# comparison_service.py
#
# Dedicated service for Document Comparison (Phase C3).
#
# Allows users to select two or more documents and generate a grounded,
# structured comparative analysis highlighting similarities, differences,
# document-exclusive points, and citations.
#
# Strictly respects Collection & Document scope boundaries -- out-of-scope
# or non-existent document IDs are rejected before retrieval.

import json
import logging
import re
from typing import Any

from config import (
    COMPARISON_MAX_CHUNKS_PER_DOC,
    COMPARISON_MAX_INPUT_CHARS,
)
from llm import LLM
from metadata_store import MetadataStore
from retrieval import HybridRetriever

logger = logging.getLogger(__name__)

COMPARISON_SYSTEM_PROMPT = """You are ContextIQ, a professional document intelligence assistant specializing in document comparison.

Given evidence passages from multiple specified documents, generate a clear, rigorous, grounded comparison that addresses the user's comparison question.

CRITICAL RULES:
1. Compare ONLY using the provided document evidence passages. Do NOT invent facts or introduce external knowledge.
2. Clearly distinguish between similarities, differences, and facts exclusive to specific documents.
3. Preserve document identity -- explicitly attribute claims to the correct source document filename.
4. If evidence is missing or insufficient to compare a specific aspect, explicitly state that in the comparison.
5. Return ONLY a JSON object matching this exact structure:

{
  "summary": "High-level comparative summary paragraph.",
  "similarities": ["Key similarity 1", "Key similarity 2"],
  "differences": ["Key difference 1", "Key difference 2"],
  "document_a_only": ["Points exclusive to the first document"],
  "document_b_only": ["Points exclusive to the second document"]
}"""


def _parse_comparison_json(raw_output: str, filenames: list[str]) -> dict[str, Any]:
    """
    Defensively parse model output into structured comparison dict.
    Supports pure JSON, markdown-fenced JSON, and bullet-point fallback.
    """
    cleaned_text = raw_output.strip()

    if "```" in cleaned_text:
        cleaned_text = re.sub(r"```(?:json)?\n?", "", cleaned_text)
        cleaned_text = cleaned_text.replace("```", "").strip()

    try:
        data = json.loads(cleaned_text)
        if isinstance(data, dict):
            return {
                "summary": str(data.get("summary", "")).strip() or "Comparison completed.",
                "similarities": [str(x).strip() for x in data.get("similarities", []) if isinstance(x, str) and x.strip()],
                "differences": [str(x).strip() for x in data.get("differences", []) if isinstance(x, str) and x.strip()],
                "document_a_only": [str(x).strip() for x in data.get("document_a_only", []) if isinstance(x, str) and x.strip()],
                "document_b_only": [str(x).strip() for x in data.get("document_b_only", []) if isinstance(x, str) and x.strip()],
            }
    except Exception:
        pass

    # Regex JSON block fallback
    match = re.search(r"(\{.*\})", raw_output, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict):
                return {
                    "summary": str(data.get("summary", "")).strip() or "Comparison completed.",
                    "similarities": [str(x).strip() for x in data.get("similarities", []) if isinstance(x, str)],
                    "differences": [str(x).strip() for x in data.get("differences", []) if isinstance(x, str)],
                    "document_a_only": [str(x).strip() for x in data.get("document_a_only", []) if isinstance(x, str)],
                    "document_b_only": [str(x).strip() for x in data.get("document_b_only", []) if isinstance(x, str)],
                }
        except Exception:
            pass

    # Line-by-line fallback text parsing
    lines = [line.strip() for line in raw_output.split("\n") if line.strip()]
    summary = lines[0] if lines else "Comparison completed."
    similarities = []
    differences = []

    for line in lines[1:]:
        clean_line = re.sub(r"^(?:[0-9]+[\.\)]|[\-\*\•\–])\s*", "", line).strip()
        if not clean_line:
            continue
        if any(w in clean_line.lower() for w in ["both", "same", "similar", "shared", "alike"]):
            similarities.append(clean_line)
        elif any(w in clean_line.lower() for w in ["differ", "unlike", "change", "only", "whereas", "however"]):
            differences.append(clean_line)
        else:
            similarities.append(clean_line)

    return {
        "summary": summary,
        "similarities": similarities,
        "differences": differences,
        "document_a_only": [],
        "document_b_only": [],
    }


class ComparisonService:
    """Service for running grounded document comparison."""

    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        llm: LLM | None = None,
    ) -> None:
        self.retriever = retriever or HybridRetriever()
        self.llm = llm or LLM()

    def compare_documents(
        self,
        filenames: list[str],
        question: str | None = None,
        collection_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Compare two or more documents with scope enforcement and grounded evidence retrieval.
        """
        if not filenames or len(filenames) < 2:
            raise ValueError("Comparison requires at least 2 documents.")

        # 1. Scope & Existence Validation
        if collection_id is not None:
            allowed_docs = MetadataStore.list_documents(collection_id=collection_id)
            allowed_set = {d["filename"] for d in allowed_docs}
            for fname in filenames:
                if fname not in allowed_set:
                    raise PermissionError(
                        f"Document '{fname}' is not accessible within collection '{collection_id}'."
                    )
        else:
            for fname in filenames:
                meta = MetadataStore.get_document_meta(fname)
                if not meta:
                    raise ValueError(f"Document '{fname}' does not exist in the knowledge base.")

        effective_question = (
            question.strip()
            if question and question.strip()
            else "Compare the key findings, metrics, and changes between these documents."
        )

        # 2. Per-Document Scoped Evidence Retrieval
        all_chunks: list[dict] = []
        doc_evidence_blocks: list[str] = []
        total_chars = 0

        for idx, fname in enumerate(filenames, 1):
            chunks = self.retriever.retrieve(
                query=effective_question,
                top_k=COMPARISON_MAX_CHUNKS_PER_DOC,
                document_filter=fname,
                collection_id=collection_id,
            )
            # Fallback if no specific chunks matched the query
            if not chunks:
                chunks = self.retriever.retrieve(
                    query="overview summary key points metrics",
                    top_k=COMPARISON_MAX_CHUNKS_PER_DOC,
                    document_filter=fname,
                    collection_id=collection_id,
                )

            all_chunks.extend(chunks)

            # Build document-labeled text snippet
            snippets = []
            for c in chunks:
                snippets.append(c.get("chunk_text", ""))

            doc_text = "\n".join(snippets)
            block = f"DOCUMENT {idx} ({fname}):\n{doc_text}"

            if total_chars + len(block) > COMPARISON_MAX_INPUT_CHARS:
                rem = COMPARISON_MAX_INPUT_CHARS - total_chars
                if rem > 100:
                    doc_evidence_blocks.append(block[:rem] + "...")
                break

            doc_evidence_blocks.append(block)
            total_chars += len(block)

        if not all_chunks:
            return {
                "filenames": filenames,
                "question": effective_question,
                "summary": "Insufficient evidence available to compare the selected documents.",
                "similarities": [],
                "differences": [],
                "document_a_only": [],
                "document_b_only": [],
                "sources": [],
            }

        # 3. Formulate Prompt & Generate Comparison
        evidence_str = "\n\n".join(doc_evidence_blocks)
        user_prompt = (
            f"Comparison Question: {effective_question}\n\n"
            f"Document Evidence Passages:\n\n{evidence_str}\n\n"
            f"Generate a structured JSON comparison according to the required format."
        )

        raw_response = self.llm.generate(
            system_prompt=COMPARISON_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            format="json",
        )

        parsed = _parse_comparison_json(raw_response, filenames)

        # 4. Process Source Citations
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
            for chunk in all_chunks
        ]

        # Enrich preview text & metadata on sources
        from api.services.rag_service import RagService
        rag_service = RagService()
        rag_service._enrich_sources(sources)

        return {
            "filenames": filenames,
            "question": effective_question,
            "summary": parsed["summary"],
            "similarities": parsed["similarities"],
            "differences": parsed["differences"],
            "document_a_only": parsed["document_a_only"],
            "document_b_only": parsed["document_b_only"],
            "sources": sources,
        }
