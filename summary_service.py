# summary_service.py
#
# Dedicated automatic document summarization service for ContextIQ 2.0 Phase C1.
# Generates concise, grounded summaries and key points for indexed documents
# using local Ollama LLM infrastructure with bounded computation and local persistence.

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from config import (
    DATA_DIR,
    SUMMARY_ENABLED,
    SUMMARY_MAX_CHUNKS,
    SUMMARY_MAX_INPUT_CHARS,
    SUMMARY_MAX_KEY_POINTS,
    SUMMARY_MODEL_NAME,
)
from llm import LLM
from metadata_store import MetadataStore
from parsers import default_registry

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """You are an expert document intelligence assistant summarizing a private document.
Your task is to analyze the provided document content and output a structured JSON object containing:
1. "summary": A concise 2-5 sentence overview summarizing the main subject, purpose, key findings, and conclusions of the document.
2. "key_points": A list of 3-7 bullet points highlighting essential facts, figures, findings, recommendations, or dates.

Strict Rules:
- Base your output ONLY on the supplied document text. Do NOT invent facts or use external knowledge.
- Keep the summary objective and accurate to the source text.
- If information on a topic is unavailable, do not speculate.
- Return ONLY valid JSON matching this schema: {"summary": "...", "key_points": ["...", "..."]}
"""

INTERMEDIATE_SUMMARY_PROMPT = """Synthesize the following section of a document into 2-3 key takeaways preserving essential facts, names, and numbers.
Section Text:
{text}
"""

FINAL_SYNTHESIS_PROMPT = """Below are key summary excerpts from different parts of a document.
Synthesize these excerpts into a final structured JSON summary matching the schema:
{"summary": "2-5 sentence executive summary...", "key_points": ["key point 1", "key point 2", "key point 3"]}

Excerpts:
{excerpts}
"""


class SummaryService:
    """Service handling automatic document summarization, persistence, and retries."""

    def __init__(self, llm: Optional[LLM] = None) -> None:
        self.llm = llm or LLM(model=SUMMARY_MODEL_NAME)

    def _parse_llm_json(self, raw_text: str) -> Dict[str, Any]:
        """
        Robustly parse JSON output from the LLM, handling markdown codeblocks
        and fallback text formatting.
        """
        cleaned = raw_text.strip()
        # Remove ```json ... ``` codeblocks if present
        if "```" in cleaned:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
            if match:
                cleaned = match.group(1)
            else:
                cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned).strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                summary = str(data.get("summary", "")).strip()
                raw_points = data.get("key_points", [])
                if isinstance(raw_points, list):
                    key_points = [str(p).strip() for p in raw_points if str(p).strip()]
                elif isinstance(raw_points, str):
                    key_points = [p.strip(" *-•") for p in raw_points.split("\n") if p.strip()]
                else:
                    key_points = []
                return {
                    "summary": summary or raw_text.strip(),
                    "key_points": key_points[:SUMMARY_MAX_KEY_POINTS],
                }
        except json.JSONDecodeError:
            logger.warning("LLM response was not valid JSON; applying fallback parsing.")

        # Fallback regex extraction
        summary_match = re.search(r'"summary"\s*:\s*"(.*?)"', cleaned, re.DOTALL)
        summary_val = summary_match.group(1).replace("\\n", "\n") if summary_match else cleaned

        points_match = re.findall(r'"(.*?)"', cleaned)
        fallback_points = [p for p in points_match if len(p) > 10 and p != summary_val][:SUMMARY_MAX_KEY_POINTS]

        if not fallback_points:
            # Extract bullet points from text lines
            lines = [l.strip(" *-•") for l in cleaned.split("\n") if l.strip().startswith(("-", "*", "•", "1.", "2."))]
            fallback_points = lines[:SUMMARY_MAX_KEY_POINTS]

        return {
            "summary": summary_val,
            "key_points": fallback_points,
        }

    def _sample_large_text(self, full_text: str) -> str:
        """
        Sample head, middle, and tail content for large documents up to SUMMARY_MAX_INPUT_CHARS.
        """
        total_len = len(full_text)
        if total_len <= SUMMARY_MAX_INPUT_CHARS:
            return full_text

        part_size = SUMMARY_MAX_INPUT_CHARS // 3
        head = full_text[:part_size]
        mid_start = (total_len // 2) - (part_size // 2)
        mid = full_text[mid_start : mid_start + part_size]
        tail = full_text[-part_size:]

        return f"{head}\n\n[... middle section excerpt ...]\n\n{mid}\n\n[... final section excerpt ...]\n\n{tail}"

    def summarize_document(self, filename: str, force: bool = False) -> Dict[str, Any]:
        """
        Generate and persist a grounded summary for a document.

        Guarantees:
        - Safe failure isolation: returns status='failed' if Ollama is unreachable or errors out.
        - Idempotent: reuses existing completed summary unless force=True.
        - Bounded: limits input tokens and LLM calls.
        """
        if not SUMMARY_ENABLED and not force:
            logger.info("Summarization disabled in config; skipping for '%s'", filename)
            return {"document_id": filename, "filename": filename, "status": "pending", "summary": "", "key_points": []}

        # Check existing summary
        existing = MetadataStore.get_summary(filename)
        if existing and existing.get("status") == "completed" and not force:
            logger.info("Reusing existing summary for '%s'", filename)
            return existing

        # Mark as generating
        MetadataStore.update_summary_status(filename, status="generating")

        file_path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(file_path):
            err_msg = f"Document file '{filename}' not found in data folder"
            MetadataStore.update_summary_status(filename, status="failed", error=err_msg)
            return MetadataStore.get_summary(filename) or {"filename": filename, "status": "failed", "error": err_msg}

        try:
            parser = default_registry.get_parser(filename)
            if not parser:
                raise ValueError(f"No parser available for '{filename}'")

            norm_doc = parser.parse(file_path)
            full_text = norm_doc.text.strip()

            if not full_text:
                summary_data = {
                    "summary": "No readable text content found in document.",
                    "key_points": [],
                }
            else:
                sampled_text = self._sample_large_text(full_text)
                user_prompt = f"Document Filename: {filename}\nDocument Type: {norm_doc.file_type}\nExtraction Method: {norm_doc.extraction_method}\n\nDocument Content:\n{sampled_text}"

                raw_response = self.llm.generate(
                    system_prompt=SUMMARY_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    format="json",
                )
                summary_data = self._parse_llm_json(raw_response)

            saved = MetadataStore.save_summary(
                filename=filename,
                summary=summary_data["summary"],
                key_points=summary_data["key_points"],
                status="completed",
            )
            logger.info("Successfully generated summary for '%s'", filename)
            return saved

        except Exception as e:
            logger.exception("Failed to generate summary for '%s'", filename)
            err_str = str(e)
            saved = MetadataStore.update_summary_status(filename, status="failed", error=err_str)
            return saved or {"filename": filename, "status": "failed", "error": err_str, "summary": "", "key_points": []}

    def get_summary(self, filename: str) -> Optional[Dict[str, Any]]:
        """Fetch existing summary for a document from SQLite."""
        return MetadataStore.get_summary(filename)

    def delete_summary(self, filename: str) -> bool:
        """Delete stored summary for a document."""
        return MetadataStore.delete_summary(filename)
