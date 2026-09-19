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

from citation_verification_service import CitationVerificationService
from config import TOP_K
from llm import LLM
from retrieval import HybridRetriever
from suggested_question_service import SuggestedQuestionService

# Backward-compatibility alias: code that imports "from rag import Retriever"
# (including tests) continues to work; new code should use HybridRetriever.
Retriever = HybridRetriever

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
        + (f" [Slide {chunk['slide']}]" if chunk.get("slide") else "")
        + (f" [Sheet: {chunk['sheet']}]" if chunk.get("sheet") else "")
        + (f" [Section: {chunk['section']}]" if chunk.get("section") else "")
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
    collection_id: str | None = None,
    tag: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """
    Full RAG pipeline for one question: retrieve, then generate.
    """
    retriever = retriever or Retriever()
    llm = llm or LLM()

    chunks = retriever.retrieve(
        question,
        document_filter=document_filter,
        collection_id=collection_id,
        tag=tag,
        tags=tags,
    )
    if not chunks:
        return {
            "answer": "I don't know based on the provided documents.",
            "sources": [],
            "suggested_questions": [],
            "citation_verification": [],
        }

    prompt = build_prompt(question, chunks)
    safe_history = (history or [])[-6:]
    answer = llm.generate(SYSTEM_PROMPT, prompt, history=safe_history)

    sources = [
        {
            "filename": chunk["filename"],
            "chunk_id": chunk["chunk_id"],
            "similarity": chunk["similarity"],
            "page": chunk.get("page"),
            "slide": chunk.get("slide"),
            "sheet": chunk.get("sheet"),
            "section": chunk.get("section"),
            "extraction_method": chunk.get("extraction_method"),
            "document_id": chunk.get("document_id"),
        }
        for chunk in chunks
    ]

    suggested_questions = []
    try:
        suggested_service = SuggestedQuestionService(llm=LLM())
        suggested_questions = suggested_service.generate_suggestions(
            question, answer, chunks
        )
    except Exception:
        suggested_questions = []

    citation_verification = []
    try:
        verification_service = CitationVerificationService(llm=LLM())
        citation_verification = verification_service.verify_citations(
            answer, chunks
        )
    except Exception:
        citation_verification = []

    return {
        "answer": answer,
        "sources": sources,
        "suggested_questions": suggested_questions,
        "citation_verification": citation_verification,
    }


def answer_question_stream(
    question: str,
    retriever: Retriever | None = None,
    llm: LLM | None = None,
    history: list[dict] | None = None,
    document_filter: str | None = None,
    collection_id: str | None = None,
    tag: str | None = None,
    tags: list[str] | None = None,
) -> Iterator[dict]:
    """
    Streaming counterpart to answer_question(): identical retrieval
    step and identical grounding policy, but yields the answer
    incrementally instead of returning it all at once.
    """
    retriever = retriever or Retriever()
    llm = llm or LLM()

    chunks = retriever.retrieve(
        question,
        document_filter=document_filter,
        collection_id=collection_id,
        tag=tag,
        tags=tags,
    )

    sources = [
        {
            "filename": chunk["filename"],
            "chunk_id": chunk["chunk_id"],
            "similarity": chunk["similarity"],
            "page": chunk.get("page"),
            "section": chunk.get("section"),
            "document_id": chunk.get("document_id"),
        }
        for chunk in chunks
    ]
    yield {"type": "sources", "sources": sources}

    if not chunks:
        yield {
            "type": "token",
            "text": "I don't know based on the provided documents.",
        }
        yield {"type": "suggested_questions", "questions": []}
        yield {"type": "citation_verification", "verifications": []}
        return

    prompt = build_prompt(question, chunks)
    safe_history = (history or [])[-6:]

    # Coalesce the model's raw token stream into phrase/sentence-sized
    # pieces before emitting. The streamed TEXT is identical, but the
    # client receives far fewer, larger updates -- smoother to read and a
    # fraction of the re-renders (Markdown is re-parsed on each update).
    # Flush on sentence end / newline, or once a buffer passes ~48 chars
    # at a word boundary, so the first words still appear promptly.
    full_answer = ""
    buffer = ""
    for delta in llm.generate_stream(SYSTEM_PROMPT, prompt, history=safe_history):
        full_answer += delta
        buffer += delta
        if buffer[-1:] in ".!?\n" or (len(buffer) >= 48 and buffer[-1:] == " "):
            yield {"type": "token", "text": buffer}
            buffer = ""
    if buffer:
        yield {"type": "token", "text": buffer}

    try:
        suggested_service = SuggestedQuestionService(llm=LLM())
        suggestions = suggested_service.generate_suggestions(
            question, full_answer, chunks
        )
        if suggestions:
            yield {"type": "suggested_questions", "questions": suggestions}
    except Exception:
        pass

    try:
        verification_service = CitationVerificationService(llm=LLM())
        verifications = verification_service.verify_citations(
            full_answer, chunks
        )
        if verifications:
            yield {"type": "citation_verification", "verifications": verifications}
    except Exception:
        pass


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
