# rag.py
#
# The "retrieval" side of the RAG pipeline: takes a user question,
# embeds it with the SAME model used at ingestion time, and asks the
# Chroma vector database (via vector_store.py) for the most similar
# chunks.
#
# Kept separate from ingest.py so querying doesn't depend on ingestion
# logic; the API layer imports from here without knowing how retrieval
# works internally.
#
# Answer generation works the same way in reverse: retrieved chunks
# are combined with the user question into a grounded prompt, sent
# to a local Ollama model (via llm.py), and returned together with
# the sources used.

from collections.abc import Iterator

import chromadb.errors

from config import BGE_QUERY_PREFIX, TOP_K
from embedding_model import get_embedding_model
from llm import LLM
from vector_store import get_collection

# Grounding instructions sent as the system message on every request.
# This is what keeps the bot honest: it must answer from the supplied
# context only, and must say it doesn't know rather than guess.
SYSTEM_PROMPT = """You are a document assistant.

Answer ONLY from the provided context.

If the answer is not present, reply exactly:

'I don't know based on the provided documents.'

Do not invent information."""


class Retriever:
    """
    Reusable semantic retriever over the Chroma knowledge base.

    Loads the embedding model and opens the database ONCE at
    construction, so a single Retriever instance can serve many
    queries cheaply (important later, when the Streamlit app keeps
    one instance alive across user questions).
    """

    def __init__(self) -> None:
        """
        Get the shared embedding model and open the vector database.

        The model comes from embedding_model.py's process-wide
        singleton — the SAME instance ingest.py uses to embed chunks
        at indexing time, not just the same model name. Vectors from
        different models (or even different loaded instances of
        weights that drifted) would live in incompatible spaces, so
        sharing the instance is what keeps similarity scores
        meaningful; sharing it also means a process never holds two
        ~130MB copies of the model in memory at once.
        """
        self.model = get_embedding_model()
        self.collection = get_collection()

    def embed_query(self, query: str) -> list[float]:
        """
        Convert a user query into an embedding vector.

        BGE models were trained so that short search queries get an
        instruction prefix before embedding (documents do not). Adding
        it here measurably improves retrieval quality while keeping
        the stored chunk vectors untouched.
        """
        vector = self.model.encode(BGE_QUERY_PREFIX + query)
        return vector.tolist()

    def retrieve(self, query: str, top_k: int = TOP_K) -> list[dict]:
        """
        Return the top_k chunks most relevant to the query.

        Each result dict contains:
            similarity  -> float in [0, 1], higher = more relevant
            filename    -> source document the chunk came from
            chunk_id    -> unique id of the chunk in the database
            chunk_text  -> the chunk's actual text

        How it works: the query is embedded, then Chroma performs a
        nearest-neighbour search against the stored chunk vectors.
        The collection uses cosine DISTANCE (0 = identical), so we
        convert to a more intuitive similarity via 1 - distance.
        """
        # The collection handle is bound to a specific Chroma
        # collection id at construction time. If another process
        # (a CLI reindex, a test run) deleted and recreated it since,
        # that id no longer exists — reopen by name once and retry
        # rather than surfacing a crash for what's really just a
        # cache gone stale.
        try:
            count = self.collection.count()
        except chromadb.errors.NotFoundError:
            self.collection = get_collection()
            count = self.collection.count()

        # An empty database can't answer anything — return early
        # instead of letting Chroma raise on n_results > 0 hits.
        if count == 0:
            return []

        try:
            results = self.collection.query(
                query_embeddings=[self.embed_query(query)],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
        except chromadb.errors.NotFoundError:
            self.collection = get_collection()
            results = self.collection.query(
                query_embeddings=[self.embed_query(query)],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

        # Chroma returns parallel lists (one entry per query; we sent
        # one query, hence the [0]s). Zip them back into one dict per
        # retrieved chunk.
        hits: list[dict] = []
        for chunk_id, text, meta, distance in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append(
                {
                    "similarity": 1.0 - distance,
                    "filename": meta["filename"],
                    "chunk_id": chunk_id,
                    "chunk_text": text,
                }
            )
        return hits


def print_results(query: str, results: list[dict]) -> None:
    """
    Pretty-print retrieval results for one query to the console.

    Shows rank, similarity score, source file, chunk id, and a
    trimmed preview of the chunk text so the output stays readable.
    """
    print(f"\n{'=' * 70}")
    print(f"QUERY: {query}")
    print("=" * 70)

    if not results:
        print("No results — the database is empty. Run ingest.py first.")
        return

    for rank, r in enumerate(results, 1):
        preview = r["chunk_text"][:200].replace("\n", " ")
        print(f"\n[{rank}] similarity={r['similarity']:.4f}  "
              f"file={r['filename']}  id={r['chunk_id']}")
        print(f"    {preview}...")


def build_prompt(question: str, chunks: list[dict]) -> str:
    """
    Assemble the user prompt from retrieved chunks plus the question.

    Each chunk becomes a numbered, labelled context block (the label
    carries filename and chunk_id, which lets the model — and anyone
    reading the prompt — see where each passage came from). The
    question goes last, after the context, which is the ordering
    instruction-tuned models follow best.
    """
    context_blocks = [
        f"[Source {i}: {chunk['filename']} ({chunk['chunk_id']})]\n{chunk['chunk_text']}"
        for i, chunk in enumerate(chunks, 1)
    ]
    context = "\n\n".join(context_blocks)
    return f"Context:\n\n{context}\n\nQuestion: {question}"


def answer_question(
    question: str,
    retriever: Retriever | None = None,
    llm: LLM | None = None,
) -> dict:
    """
    Full RAG pipeline for one question: retrieve, then generate.

    Args:
        question: The user's natural-language question.
        retriever / llm: Existing instances to reuse (so callers like
            the future Streamlit app avoid reloading the embedding
            model per question). Created fresh if not supplied.

    Returns a dict with:
        answer  -> the model's grounded reply (str)
        sources -> list of {filename, chunk_id, similarity} for the
                   chunks the answer was based on

    If retrieval finds nothing (empty database), the LLM is not
    called at all — we return the honest fallback reply directly.
    """
    retriever = retriever or Retriever()
    llm = llm or LLM()

    chunks = retriever.retrieve(question)
    if not chunks:
        return {
            "answer": "I don't know based on the provided documents.",
            "sources": [],
        }

    answer = llm.generate(SYSTEM_PROMPT, build_prompt(question, chunks))

    # Return only source metadata (not full chunk text) — enough for
    # the caller to cite or display where the answer came from.
    sources = [
        {
            "filename": chunk["filename"],
            "chunk_id": chunk["chunk_id"],
            "similarity": chunk["similarity"],
        }
        for chunk in chunks
    ]
    return {"answer": answer, "sources": sources}


def answer_question_stream(
    question: str,
    retriever: Retriever | None = None,
    llm: LLM | None = None,
) -> Iterator[dict]:
    """
    Streaming counterpart to answer_question(): identical retrieval
    step and identical grounding policy, but yields the answer
    incrementally instead of returning it all at once.

    Yields a sequence of event dicts:
        {"type": "sources", "sources": [...]} -> exactly once, first
        {"type": "token", "text": "..."}      -> zero or more times

    The empty-database fallback is delivered as a single "token"
    event carrying the exact same wording answer_question() returns,
    and — just like answer_question() — the LLM is never called when
    there is nothing to answer from.
    """
    retriever = retriever or Retriever()
    llm = llm or LLM()

    chunks = retriever.retrieve(question)
    sources = [
        {
            "filename": chunk["filename"],
            "chunk_id": chunk["chunk_id"],
            "similarity": chunk["similarity"],
        }
        for chunk in chunks
    ]
    yield {"type": "sources", "sources": sources}

    if not chunks:
        yield {
            "type": "token",
            "text": "I don't know based on the provided documents.",
        }
        return

    prompt = build_prompt(question, chunks)
    for delta in llm.generate_stream(SYSTEM_PROMPT, prompt):
        yield {"type": "token", "text": delta}


def main() -> None:
    """Run end-to-end verification: retrieval + grounded generation."""
    # Build the expensive objects once and reuse them for all queries.
    retriever = Retriever()
    llm = LLM()

    for query in [
        "What is semantic memory?",
        "How does Zephyra store knowledge?",
    ]:
        result = answer_question(query, retriever, llm)

        print(f"\n{'=' * 70}")
        print(f"QUESTION: {query}")
        print("=" * 70)
        print(f"\nANSWER:\n{result['answer']}")
        print("\nSOURCES:")
        for s in result["sources"]:
            print(f"  - {s['filename']} ({s['chunk_id']}), "
                  f"similarity={s['similarity']:.4f}")


if __name__ == "__main__":
    main()
