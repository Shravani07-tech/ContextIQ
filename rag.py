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
#
# The instructions explicitly allow synthesis/inference from the context
# (not just verbatim extraction): questions like "what problem does this
# paper solve?" are answerable from an abstract that describes the
# problem without ever using the word "problem", and the earlier,
# stricter wording made the model refuse those. Grounding is preserved --
# it still answers ONLY from context, uses no outside knowledge, and
# falls back to the exact "I don't know" line when the answer truly
# isn't present.
SYSTEM_PROMPT = """You are ContextIQ, a professional document assistant. Answer the user's question using ONLY the information in the provided context.

- Ground every answer in the context. You may read across the sources to synthesise, summarise, compare, list key points, explain in simpler terms, and draw reasonable conclusions -- the answer need not appear as a single verbatim sentence.
- A document's title, authors, purpose, contributions, limitations, and future work can be inferred from its front matter, abstract, and closing sections.
- Keep answers focused and brief: a few sentences, or a short bulleted list of only the key points. Do not pad, do not repeat the context back verbatim, and elaborate further only if the user explicitly asks.
- Only if the context genuinely lacks the information needed to answer, reply exactly:

'I don't know based on the provided documents.'

- Never use outside knowledge, and never invent facts the context does not support."""


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
        singleton -- the SAME instance ingest.py uses to embed chunks
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

    def retrieve(
        self,
        query: str,
        top_k: int = TOP_K,
        document_filter: str | None = None,
    ) -> list[dict]:
        """
        Return the top_k chunks most relevant to the query.

        Args:
            query:           The user's question.
            top_k:           Maximum number of chunks to return.
            document_filter: When set, restrict retrieval to this filename only.
                             None means retrieve across ALL indexed documents.

        Each result dict contains:
            similarity  -> float in [0, 1], higher = more relevant
            filename    -> source document the chunk came from
            chunk_id    -> unique id of the chunk in the database
            chunk_text  -> the chunk's actual text

        How it works: the query is embedded, then Chroma performs a
        nearest-neighbour search against the stored chunk vectors.
        The collection uses cosine DISTANCE (0 = identical), so we
        convert to a more intuitive similarity via 1 - distance.

        Document filtering: when document_filter is provided, only
        chunks whose metadata['filename'] matches are returned.
        This enforces hard document isolation in Selected-Document mode.
        """
        # The collection handle is bound to a specific Chroma
        # collection id at construction time. If another process
        # (a CLI reindex, a test run) deleted and recreated it since,
        # that id no longer exists -- reopen by name once and retry
        # rather than surfacing a crash for what's really just a
        # cache gone stale.
        try:
            count = self.collection.count()
        except chromadb.errors.NotFoundError:
            self.collection = get_collection()
            count = self.collection.count()

        # An empty database can't answer anything -- return early
        # instead of letting Chroma raise on n_results > 0 hits.
        if count == 0:
            return []

        # When filtering to a specific document, verify it actually exists
        # before querying -- prevents spurious empty results for typos or
        # deleted documents.
        if document_filter:
            filter_clause = {"filename": document_filter}
            # Count chunks for this specific document
            try:
                doc_records = self.collection.get(
                    where=filter_clause, include=[], limit=1
                )
                if not doc_records["ids"]:
                    return []  # Document does not exist -- honest empty result
            except chromadb.errors.NotFoundError:
                self.collection = get_collection()
                return []
        else:
            filter_clause = None

        query_vec = self.embed_query(query)
        try:
            query_kwargs: dict = dict(
                query_embeddings=[query_vec],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
            if filter_clause:
                query_kwargs["where"] = filter_clause

            results = self.collection.query(**query_kwargs)
        except chromadb.errors.NotFoundError:
            self.collection = get_collection()
            results = self.collection.query(**query_kwargs)

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
                    # Citation metadata (populated if stored during ingestion)
                    "page": meta.get("page"),
                    "section": meta.get("section"),
                }
            )

        self._ensure_document_boundaries(hits, query_vec, document_filter)
        return hits

    # A document's opening chunks are its front matter (title, authors,
    # abstract); its final chunks are its closing sections (conclusion,
    # limitations, future work). Whole-document questions target one or
    # the other, so both boundaries are guaranteed into the context.
    #
    # Benchmarked defaults (Phase 2/3): TOP_K=4, HEAD=2, TAIL=1.
    # These values reduced prompt tokens by ~18% with no observed quality loss.
    HEAD_CHUNKS = 2
    TAIL_CHUNKS = 1
    _HEAD_LABEL = "[Document front matter]\n"
    _TAIL_LABEL = "[Document closing section]\n"

    def _ensure_document_boundaries(
        self,
        hits: list[dict],
        query_vec: list[float],
        document_filter: str | None = None,
    ) -> None:
        """
        Guarantee the dominant document's opening AND closing chunks are
        in the results, in place.

        Whole-document questions ("what is the title?", "who are the
        authors?", "what is the conclusion?", "what future work is
        suggested?") embed poorly against the text that answers them --
        a title does not sit near "what is the title" in vector space.
        We fetch boundary chunks directly (by id) for whichever document
        dominates the retrieved set, score them honestly, label them,
        and merge any that are missing.

        DOCUMENT SELECTION -- root-cause fix for cross-document
        contamination:

        We no longer anchor on hits[0] (the single top-scoring chunk).
        When multiple documents are indexed, the top-1 chunk may belong
        to a different document than the one the user is actually asking
        about -- especially for whole-document queries whose phrasing
        does not match any specific chunk well.

        Instead we select the document with the HIGHEST AGGREGATE
        similarity score across all retrieved chunks: whichever document
        contributed the most relevant content in total is the one whose
        boundaries we inject. This is robust to the case where a single
        chunk from document B outranks all chunks from document A, while
        document A dominates the rest of the result set.

        When document_filter is set, boundaries are ONLY injected for
        that document, enforcing strict document isolation.
        """
        if not hits:
            return

        # In single-document filter mode, the anchor is always the filtered doc.
        if document_filter:
            top_doc = document_filter
        else:
            # Aggregate similarity per document across all retrieved chunks.
            doc_scores: dict[str, float] = {}
            for h in hits:
                doc_scores[h["filename"]] = (
                    doc_scores.get(h["filename"], 0.0) + h["similarity"]
                )
            top_doc = max(doc_scores, key=lambda d: doc_scores[d])

        # Chunk ids are "<filename>-<n>"; find this document's index range.
        all_ids = self.collection.get(where={"filename": top_doc}, include=[])[
            "ids"
        ]
        indices = sorted(
            int(cid.rsplit("-", 1)[1])
            for cid in all_ids
            if cid.rsplit("-", 1)[1].isdigit()
        )
        if not indices:
            return

        head_idx = set(indices[: self.HEAD_CHUNKS])
        tail_idx = set(indices[-self.TAIL_CHUNKS :]) - head_idx  # tiny docs: head wins
        labels = {f"{top_doc}-{i}": self._HEAD_LABEL for i in head_idx}
        labels.update({f"{top_doc}-{i}": self._TAIL_LABEL for i in tail_idx})

        present = {h["chunk_id"] for h in hits}
        missing = [cid for cid in labels if cid not in present]
        if not missing:
            return

        records = self.collection.get(
            ids=missing, include=["documents", "embeddings", "metadatas"]
        )
        q_norm = sum(v * v for v in query_vec) ** 0.5 or 1.0
        head_hits: list[dict] = []
        tail_hits: list[dict] = []
        for chunk_id, text, emb, meta in zip(
            records["ids"],
            records["documents"],
            records["embeddings"],
            records["metadatas"],
        ):
            # Cosine similarity, matching the 1 - cosine_distance the main
            # query path reports, so sources stay comparable.
            e_norm = sum(v * v for v in emb) ** 0.5 or 1.0
            similarity = sum(a * b for a, b in zip(query_vec, emb)) / (q_norm * e_norm)
            entry = {
                "similarity": similarity,
                "filename": meta["filename"],
                "chunk_id": chunk_id,
                # Labels are prompt-only; the stored chunk and the source
                # preview shown in the UI (fetched separately) are untouched.
                "chunk_text": labels[chunk_id] + text,
                "page": meta.get("page"),
                "section": meta.get("section"),
            }
            idx = int(chunk_id.rsplit("-", 1)[1])
            (head_hits if idx in head_idx else tail_hits).append(entry)

        head_hits.sort(key=lambda h: int(h["chunk_id"].rsplit("-", 1)[1]))
        tail_hits.sort(key=lambda h: int(h["chunk_id"].rsplit("-", 1)[1]))
        hits[:0] = head_hits      # opening first
        hits.extend(tail_hits)    # closing last


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
        print("No results -- the database is empty. Run ingest.py first.")
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
    carries filename and chunk_id, which lets the model -- and anyone
    reading the prompt -- see where each passage came from). The
    question goes last, after the context, which is the ordering
    instruction-tuned models follow best.
    """
    context_blocks = [
        f"[Source {i}: {chunk['filename']} ({chunk['chunk_id']})]"
        + (f" [Page {chunk['page']}]" if chunk.get("page") else "")
        + f"\n{chunk['chunk_text']}"
        for i, chunk in enumerate(chunks, 1)
    ]
    context = "\n\n".join(context_blocks)
    return f"Context:\n\n{context}\n\nQuestion: {question}"


def answer_question(
    question: str,
    retriever: Retriever | None = None,
    llm: LLM | None = None,
    history: list[dict] | None = None,
    document_filter: str | None = None,
) -> dict:
    """
    Full RAG pipeline for one question: retrieve, then generate.

    Args:
        question:        The user's natural-language question.
        retriever / llm: Existing instances to reuse. Created fresh if not supplied.
        history:         Prior conversation turns [{role, content}, ...].
                         Sent to the LLM as context; does NOT affect retrieval.
                         Capped at 6 messages by the schema; enforced here too.
        document_filter: When set, restricts retrieval to this document only.

    Returns a dict with:
        answer  -> the model's grounded reply (str)
        sources -> list of {filename, chunk_id, similarity, page, section} for the
                   chunks the answer was based on

    If retrieval finds nothing (empty database), the LLM is not
    called at all -- we return the honest fallback reply directly.
    """
    retriever = retriever or Retriever()
    llm = llm or LLM()

    chunks = retriever.retrieve(question, document_filter=document_filter)
    if not chunks:
        return {
            "answer": "I don't know based on the provided documents.",
            "sources": [],
        }

    prompt = build_prompt(question, chunks)
    safe_history = (history or [])[-6:]
    answer = llm.generate(SYSTEM_PROMPT, prompt, history=safe_history)

    # Return only source metadata (not full chunk text) -- enough for
    # the caller to cite or display where the answer came from.
    sources = [
        {
            "filename": chunk["filename"],
            "chunk_id": chunk["chunk_id"],
            "similarity": chunk["similarity"],
            "page": chunk.get("page"),
            "section": chunk.get("section"),
        }
        for chunk in chunks
    ]
    return {"answer": answer, "sources": sources}


def answer_question_stream(
    question: str,
    retriever: Retriever | None = None,
    llm: LLM | None = None,
    history: list[dict] | None = None,
    document_filter: str | None = None,
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
    and -- just like answer_question() -- the LLM is never called when
    there is nothing to answer from.

    Args:
        history:         Prior conversation turns -- injected as prior messages
                         in the Ollama /api/chat payload. Capped at 6.
        document_filter: Restrict retrieval to one document filename.
    """
    retriever = retriever or Retriever()
    llm = llm or LLM()

    chunks = retriever.retrieve(question, document_filter=document_filter)
    sources = [
        {
            "filename": chunk["filename"],
            "chunk_id": chunk["chunk_id"],
            "similarity": chunk["similarity"],
            "page": chunk.get("page"),
            "section": chunk.get("section"),
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
    safe_history = (history or [])[-6:]

    # Coalesce the model's raw token stream into phrase/sentence-sized
    # pieces before emitting. The streamed TEXT is identical, but the
    # client receives far fewer, larger updates -- smoother to read and a
    # fraction of the re-renders (Markdown is re-parsed on each update).
    # Flush on sentence end / newline, or once a buffer passes ~48 chars
    # at a word boundary, so the first words still appear promptly.
    buffer = ""
    for delta in llm.generate_stream(SYSTEM_PROMPT, prompt, history=safe_history):
        buffer += delta
        if buffer[-1:] in ".!?\n" or (len(buffer) >= 48 and buffer[-1:] == " "):
            yield {"type": "token", "text": buffer}
            buffer = ""
    if buffer:
        yield {"type": "token", "text": buffer}


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
