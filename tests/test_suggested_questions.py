# tests/test_suggested_questions.py
#
# Comprehensive test suite for ContextIQ 2.0 Phase C2: Suggested Follow-up Questions.
# Tests output validation, JSON parsing, duplicate removal, generic filler filtering,
# failure isolation, scope propagation, and API schema integration.

import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from rag import answer_question, answer_question_stream
from suggested_question_service import (
    SuggestedQuestionService,
    clean_and_validate_suggestions,
)


class SuggestedQuestionValidationTests(unittest.TestCase):
    def test_clean_and_validate_suggestions(self):
        current_q = "What are the major risks in this project?"
        raw = [
            "1. What evidence supports these financial risks?",
            "  * Which risks have increased over time?  ",
            "\"What mitigation measures are proposed?\"",
            "What are the major risks in this project?",  # Duplicate of current question
            "Can you tell me more?",  # Generic filler
            "What else can you tell me?",  # Generic filler
            "What evidence supports these financial risks?",  # Duplicate
            "Short",  # Too short
            "A" * 200,  # Too long
            "What recommendations does the report suggest?",
        ]

        cleaned = clean_and_validate_suggestions(raw, current_q, max_count=4)

        self.assertEqual(len(cleaned), 4)
        self.assertEqual(cleaned[0], "What evidence supports these financial risks?")
        self.assertEqual(cleaned[1], "Which risks have increased over time?")
        self.assertEqual(cleaned[2], "What mitigation measures are proposed?")
        self.assertEqual(cleaned[3], "What recommendations does the report suggest?")

    def test_json_parsing_and_regex_fallback(self):
        svc = SuggestedQuestionService(llm=MagicMock())

        # 1. Clean JSON string
        raw_json = json.dumps({"questions": ["What is step 1?", "What is step 2?"]})
        res1 = svc._parse_llm_json(raw_json)
        self.assertEqual(res1, ["What is step 1?", "What is step 2?"])

        # 2. Markdown fenced JSON string
        markdown_json = f"```json\n{raw_json}\n```"
        res2 = svc._parse_llm_json(markdown_json)
        self.assertEqual(res2, ["What is step 1?", "What is step 2?"])

        # 3. Line-by-line fallback
        bulleted = "Here are questions:\n- What evidence supports this?\n- What are the next steps?"
        res3 = svc._parse_llm_json(bulleted)
        self.assertIn("What evidence supports this?", res3)
        self.assertIn("What are the next steps?", res3)

    def test_service_failure_isolation(self):
        """Verify that LLM failure returns [] without raising an exception."""
        mock_llm = MagicMock()
        mock_llm.generate.side_effect = RuntimeError("Ollama connection timeout")
        svc = SuggestedQuestionService(llm=mock_llm)

        res = svc.generate_suggestions(
            question="What is Phase A?",
            answer="Phase A is ingestion.",
            chunks=[{"chunk_text": "Phase A details...", "filename": "doc.txt"}],
        )
        self.assertEqual(res, [])

    def test_fallback_answer_skip(self):
        """Verify that no suggestions are generated if answer is 'I don't know'."""
        mock_llm = MagicMock()
        svc = SuggestedQuestionService(llm=mock_llm)

        res = svc.generate_suggestions(
            question="What is X?",
            answer="I don't know based on the provided documents.",
            chunks=[],
        )
        self.assertEqual(res, [])
        mock_llm.generate.assert_not_called()


class SuggestedQuestionRagIntegrationTests(unittest.TestCase):
    @patch("rag.SuggestedQuestionService")
    def test_answer_question_includes_suggestions(self, mock_service_cls):
        mock_service_inst = MagicMock()
        mock_service_inst.generate_suggestions.return_value = [
            "What evidence supports this?",
            "What are the implications?",
        ]
        mock_service_cls.return_value = mock_service_inst

        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = [
            {"filename": "a.txt", "chunk_id": "a.txt-0", "similarity": 0.9, "chunk_text": "Sample text"}
        ]
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Grounded answer text."

        result = answer_question(
            question="What is in the document?",
            retriever=mock_retriever,
            llm=mock_llm,
            collection_id="col_123",
        )

        self.assertIn("suggested_questions", result)
        self.assertEqual(len(result["suggested_questions"]), 2)
        self.assertEqual(result["suggested_questions"][0], "What evidence supports this?")

    @patch("rag.SuggestedQuestionService")
    def test_answer_question_failure_isolation(self, mock_service_cls):
        """Verify answer_question succeeds even if suggestion service raises an exception."""
        mock_service_inst = MagicMock()
        mock_service_inst.generate_suggestions.side_effect = Exception("LLM crash")
        mock_service_cls.return_value = mock_service_inst

        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = [
            {"filename": "a.txt", "chunk_id": "a.txt-0", "similarity": 0.9, "chunk_text": "Sample text"}
        ]
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Grounded answer text."

        result = answer_question(
            question="What is in the document?",
            retriever=mock_retriever,
            llm=mock_llm,
        )

        self.assertEqual(result["answer"], "Grounded answer text.")
        self.assertEqual(result["suggested_questions"], [])


class SuggestedQuestionApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("api.routers.chat.RagService.ask")
    def test_chat_api_response_schema(self, mock_ask):
        mock_ask.return_value = {
            "answer": "Grounded answer.",
            "sources": [
                {
                    "filename": "doc.txt",
                    "chunk_id": "doc.txt-0",
                    "similarity": 0.9,
                    "preview": "Preview text...",
                }
            ],
            "suggested_questions": [
                "What evidence supports this?",
                "What are the key conclusions?",
            ],
        }

        res = self.client.post("/chat", json={"question": "What is the summary?"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("suggested_questions", data)
        self.assertEqual(len(data["suggested_questions"]), 2)
        self.assertEqual(data["suggested_questions"][0], "What evidence supports this?")

    @patch("api.routers.chat.RagService.ask_stream")
    def test_chat_stream_api_suggested_questions(self, mock_ask_stream):
        mock_ask_stream.return_value = iter([
            {"type": "sources", "sources": []},
            {"type": "token", "text": "Answer text"},
            {"type": "suggested_questions", "questions": ["Question 1?", "Question 2?"]},
        ])

        res = self.client.post("/chat/stream", json={"question": "What is X?"})
        self.assertEqual(res.status_code, 200)
        content = res.text
        self.assertIn("suggested_questions", content)
        self.assertIn("Question 1?", content)


if __name__ == "__main__":
    unittest.main()
