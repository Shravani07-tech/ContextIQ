# research.py
#
# Multi-document research synthesis for ContextIQ.
#
# Research Mode is a lightweight grounded orchestrator — NOT an
# autonomous agent. The pipeline is:
#
#   1. Retrieve evidence across ALL documents (hybrid retrieval, no filter)
#   2. Group retrieved chunks by document
#   3. Build ONE structured synthesis prompt
#   4. ONE LLM call to produce the structured answer
#   5. Return structured result with sources
#
# The model is explicitly instructed to:
#   - Only include sections that are supported by evidence
#   - Never fabricate information
#   - Cite sources by [Source N] reference
#   - Note contradictions and gaps if visible in the evidence
#
# Research Mode does NOT:
#   - Run one LLM call per document (too slow, too expensive)
#   - Browse the internet
#   - Synthesize from outside knowledge
#   - Guarantee perfect comparison if documents share no common topic

from __future__ import annotations

import logging
from collections.abc import Iterator

from config import TOP_K
from llm import LLM
from retrieval import HybridRetriever

logger = logging.getLogger(__name__)

# System prompt for research synthesis — more structured than chat.
RESEARCH_SYSTEM_PROMPT = """You are ContextIQ Research Mode, an expert document analyst. Your task is to synthesize information across multiple documents based ONLY on the provided context.

RULES:
- Ground every claim in the provided context. Never use outside knowledge.
- Only include sections where you have actual evidence from the context.
- Cite sources using [Source N] notation matching the numbered context blocks.
- If evidence for a section is absent, omit that section entirely rather than fabricating content.
- Note contradictions or inconsistencies you observe in the evidence.
- Keep each section focused and evidence-based.
- If the context is insufficient to answer the question at all, reply with:
  'I cannot synthesize an answer — the documents do not contain sufficient relevant information.'

RESPONSE FORMAT (only include sections where evidence exists):
## Executive Summary
[2-4 sentence synthesis of the key findings]

## Document Findings
[Per-document key findings, labeled by source document name]

## Cross-Document Comparison
[Common themes, shared findings, areas of agreement]

## Differences & Contradictions
[Conflicting claims, differing methodologies, opposing conclusions]

## Research Gaps
[What questions remain unanswered, what the documents don't cover]

## Sources Used
[List the [Source N] references used]"""


def _build_research_prompt(question: str, chunks: list[dict]) -> str:
    """
    Build the research synthesis prompt.

    Groups chunks by document in the context block so the model can
    see which evidence belongs to which source document.
    """
    # Group chunks by source document for cleaner context.
    doc_chunks: dict[str, list[dict]] = {}
    for chunk in chunks:
        fn = chunk["filename"]
        if fn not in doc_chunks:
            doc_chunks[fn] = []
        doc_chunks[fn].append(chunk)

    context_blocks: list[str] = []
    source_num = 1
    for filename, doc_chunk_list in doc_chunks.items():
        for chunk in doc_chunk_list:
            header = f"[Source {source_num}: {filename} ({chunk['chunk_id']})]"
            if chunk.get("page"):
                header += f" [Page {chunk['page']}]"
            context_blocks.append(f"{header}\n{chunk['chunk_text']}")
            source_num += 1

    context = "\n\n".join(context_blocks)
    doc_names = ", ".join(f'"{fn}"' for fn in doc_chunks)
    return (
        f"Documents in context: {doc_names}\n\n"
        f"Context:\n\n{context}\n\n"
        f"Research Question: {question}"
    )


def research_question(
    question: str,
    retriever: HybridRetriever | None = None,
    llm: LLM | None = None,
    top_k: int | None = None,
) -> dict:
    """
    Full research pipeline: hybrid retrieval across ALL docs → synthesis.

    Args:
        question:  The research question to synthesize.
        retriever: Existing HybridRetriever to reuse (created fresh if None).
        llm:       Existing LLM client to reuse (created fresh if None).
        top_k:     How many chunks to retrieve. Defaults to TOP_K * 3
                   (more evidence for cross-document synthesis).

    Returns:
        {
          "answer":  str,       # Structured synthesis
          "sources": list[dict] # Source metadata (filename, chunk_id, page, etc.)
          "doc_count": int      # How many distinct documents contributed evidence
        }
    """
    retriever = retriever or HybridRetriever()
    llm = llm or LLM()
    effective_top_k = top_k or (TOP_K * 3)

    # Retrieve from ALL documents (no filter) with extra depth.
    chunks = retriever.retrieve(question, top_k=effective_top_k, document_filter=None)

    if not chunks:
        return {
            "answer": "I cannot synthesize an answer — the documents do not contain sufficient relevant information.",
            "sources": [],
            "doc_count": 0,
        }

    # Verify we actually have multiple documents represented.
    doc_names = list({c["filename"] for c in chunks})
    doc_count = len(doc_names)

    prompt = _build_research_prompt(question, chunks)
    answer = llm.generate(RESEARCH_SYSTEM_PROMPT, prompt)

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

    return {
        "answer": answer,
        "sources": sources,
        "doc_count": doc_count,
    }


def research_question_stream(
    question: str,
    retriever: HybridRetriever | None = None,
    llm: LLM | None = None,
    top_k: int | None = None,
) -> Iterator[dict]:
    """
    Streaming counterpart to research_question().

    Yields the same event format as answer_question_stream():
        {"type": "sources", "sources": [...], "doc_count": int}  — once, first
        {"type": "token",   "text": "..."}                        — zero or more
    """
    retriever = retriever or HybridRetriever()
    llm = llm or LLM()
    effective_top_k = top_k or (TOP_K * 3)

    chunks = retriever.retrieve(question, top_k=effective_top_k, document_filter=None)
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
    doc_count = len({c["filename"] for c in chunks})

    yield {"type": "sources", "sources": sources, "doc_count": doc_count}

    if not chunks:
        yield {
            "type": "token",
            "text": "I cannot synthesize an answer — the documents do not contain sufficient relevant information.",
        }
        return

    prompt = _build_research_prompt(question, chunks)

    # Buffer into phrase-sized pieces (same approach as rag.answer_question_stream).
    buffer = ""
    for delta in llm.generate_stream(RESEARCH_SYSTEM_PROMPT, prompt):
        buffer += delta
        if buffer[-1:] in ".!?\n" or (len(buffer) >= 48 and buffer[-1:] == " "):
            yield {"type": "token", "text": buffer}
            buffer = ""
    if buffer:
        yield {"type": "token", "text": buffer}
