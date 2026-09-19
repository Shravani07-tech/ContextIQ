# suggested_question_service.py
#
# Dedicated service for generating grounded follow-up question suggestions (Phase C2).
#
# Takes the user's current question, the generated grounded answer, and the
# retrieved document chunks to produce 3-5 bounded, highly relevant follow-up
# questions a researcher would ask next.
#
# Follow-ups MUST be grounded in available context and MUST NOT introduce
# unsupported facts, generic filler, or cross-collection leakages.

import json
import logging
import re
from typing import Any

from config import (
    SUGGESTED_QUESTIONS_COUNT,
    SUGGESTED_QUESTIONS_ENABLED,
    SUGGESTED_QUESTIONS_MAX_INPUT_CHARS,
)
from llm import LLM

logger = logging.getLogger(__name__)

SUGGESTION_SYSTEM_PROMPT = """You are ContextIQ, a professional research assistant. Given a user's question, an assistant's answer, and retrieved document passages, generate 3 to 5 relevant, natural, grounded follow-up questions that a researcher would ask next.

CRITICAL RULES:
1. Questions MUST be strictly grounded in the provided document passages and current conversation. Do NOT invent facts or introduce unsupported entities, topics, or assumptions.
2. Do NOT generate generic filler like "Can you tell me more?", "What else can you tell me?", "Can you explain this?", "What are some examples?", or "Can you summarize?".
3. Do NOT repeat or rephrase the user's current question.
4. Questions should deepen understanding, explore supporting evidence, implications, details, or comparisons grounded in the context.
5. Respect document and collection scope boundaries -- do not refer to outside topics.
6. Return ONLY a JSON object with a single key "questions" containing a list of strings.

Example Output format:
{"questions": ["What evidence supports these findings?", "Which factors have changed over time?", "What recommendations does the report suggest?"]}"""

GENERIC_FILLER_PATTERNS = [
    r"can you tell me more",
    r"what else can you tell me",
    r"can you explain this",
    r"can you elaborate",
    r"what are some examples",
    r"tell me more",
    r"what else",
    r"can you summarize",
    r"what is this document about",
    r"as an ai",
    r"system prompt",
    r"json format",
    r"here are follow-up",
    r"follow-up questions",
]


def clean_and_validate_suggestions(
    raw_questions: Any,
    current_question: str,
    max_count: int = SUGGESTED_QUESTIONS_COUNT,
) -> list[str]:
    """
    Clean, validate, and deduplicate candidate follow-up questions.
    Filters out empty lines, generic filler, prompt leakage, and duplicates.
    """
    if not isinstance(raw_questions, list):
        return []

    cleaned: list[str] = []
    seen_lower: set[str] = set()
    norm_current = re.sub(r"\s+", " ", current_question.strip().lower())

    for item in raw_questions:
        if not isinstance(item, str):
            continue

        q = item.strip()

        # Remove leading numbers, bullets, markdown formatting
        q = re.sub(r"^(?:[0-9]+[\.\)]|[\-\*\•\–])\s*", "", q).strip()

        # Strip surrounding quotation marks or code ticks
        q = q.strip("\"'`")
        q = re.sub(r"\s+", " ", q).strip()

        if not q:
            continue

        # Add trailing question mark if missing
        if not q.endswith("?") and not q.endswith("."):
            q += "?"

        q_lower = q.lower()

        # Bounded length sanity check
        if len(q) < 8 or len(q) > 160:
            continue

        # Reject exact or near match with the user's current question
        if q_lower == norm_current or norm_current in q_lower:
            continue

        # Reject generic filler patterns
        if any(re.search(pat, q_lower) for pat in GENERIC_FILLER_PATTERNS):
            continue

        # Reject duplicates (case-insensitive)
        if q_lower in seen_lower:
            continue

        seen_lower.add(q_lower)
        cleaned.append(q)

        if len(cleaned) >= max_count:
            break

    return cleaned


class SuggestedQuestionService:
    """Service for generating grounded follow-up question suggestions."""

    def __init__(self, llm: LLM | None = None) -> None:
        self.llm = llm or LLM()

    def _parse_llm_json(self, raw_output: str) -> list[str]:
        """
        Defensively parse JSON from model output.
        Handles pure JSON, markdown-wrapped JSON, or regex fallback.
        """
        cleaned_text = raw_output.strip()

        # Strip markdown code fences if present
        if "```" in cleaned_text:
            cleaned_text = re.sub(r"```(?:json)?\n?", "", cleaned_text)
            cleaned_text = cleaned_text.replace("```", "").strip()

        # Direct JSON load
        try:
            data = json.loads(cleaned_text)
            if isinstance(data, dict) and "questions" in data:
                return data["questions"]
            if isinstance(data, list):
                return data
        except Exception:
            pass

        # Regex extract fallback for {"questions": [...]}
        match = re.search(r"\{\s*\"questions\"\s*:\s*(\[[^\]]+\])\s*\}", raw_output, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if isinstance(data, list):
                    return data
            except Exception:
                pass

        # Line-by-line fallback for bulleted list output
        lines = [line.strip() for line in raw_output.split("\n") if line.strip()]
        questions = []
        for line in lines:
            line_clean = re.sub(r"^(?:[0-9]+[\.\)]|[\-\*\•\–])\s*", "", line).strip().strip("\"'`")
            if line_clean.endswith("?") and len(line_clean) >= 10:
                questions.append(line_clean)

        return questions

    def generate_suggestions(
        self,
        question: str,
        answer: str,
        chunks: list[dict],
    ) -> list[str]:
        """
        Generate grounded follow-up questions for a given question, answer, and retrieved chunks.
        Guaranteed to never throw an exception -- returns [] on failure or disabled state.
        """
        if not SUGGESTED_QUESTIONS_ENABLED:
            return []

        # Do not generate suggestions if the answer is the fallback "I don't know" or empty
        if not answer or "I don't know based on the provided documents" in answer:
            return []

        try:
            # Build context snippet from chunks bounded by MAX_INPUT_CHARS
            context_pieces = []
            char_count = 0
            for chunk in chunks:
                text = chunk.get("chunk_text", "")
                filename = chunk.get("filename", "")
                piece = f"[{filename}]\n{text}"
                if char_count + len(piece) > SUGGESTED_QUESTIONS_MAX_INPUT_CHARS:
                    rem = SUGGESTED_QUESTIONS_MAX_INPUT_CHARS - char_count
                    if rem > 100:
                        context_pieces.append(piece[:rem] + "...")
                    break
                context_pieces.append(piece)
                char_count += len(piece)

            context_str = "\n\n".join(context_pieces)

            user_prompt = (
                f"User Question: {question}\n\n"
                f"Generated Answer: {answer}\n\n"
                f"Retrieved Context:\n{context_str}\n\n"
                f"Generate 3 to 5 grounded follow-up questions in JSON format."
            )

            raw_response = self.llm.generate(
                system_prompt=SUGGESTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                format="json",
            )

            raw_questions = self._parse_llm_json(raw_response)
            return clean_and_validate_suggestions(raw_questions, question)
        except Exception as e:
            logger.warning(f"Failed to generate suggested follow-up questions: {e}")
            return []
