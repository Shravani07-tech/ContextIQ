# tests/test_unit.py
#
# Fast, dependency-light unit tests for the RAG core — the CI-friendly
# counterpart to test_api.py / test_app.py (which need a live Ollama
# and a populated Chroma DB). Everything external (the Ollama HTTP
# call, the Chroma collection) is mocked, so these run anywhere Python
# runs, in milliseconds, with no services and no network.
#
# Uses the stdlib unittest framework (no pytest dependency to install).
# Run with:  python -m unittest tests.test_unit -v
#            (from the project root, so the root modules import.)

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from api.services.rag_service import PREVIEW_CHARS, RagService
from ingest import chunk_documents
from llm import LLM
from rag import answer_question, answer_question_stream, build_prompt


def make_chunk(chunk_id: str, text: str, similarity: float = 0.8) -> dict:
    return {
        "filename": "doc.txt",
        "chunk_id": chunk_id,
        "chunk_text": text,
        "similarity": similarity,
    }


class BuildPromptTests(unittest.TestCase):
    def test_numbers_each_source_and_puts_the_question_last(self):
        chunks = [make_chunk("doc.txt-0", "Alpha"), make_chunk("doc.txt-1", "Beta")]
        prompt = build_prompt("What is it?", chunks)

        self.assertIn("[Source 1: doc.txt (doc.txt-0)]", prompt)
        self.assertIn("[Source 2: doc.txt (doc.txt-1)]", prompt)
        self.assertIn("Alpha", prompt)
        # Instruction-tuned models follow context-then-question best.
        self.assertLess(prompt.index("Alpha"), prompt.index("Question:"))
        self.assertTrue(prompt.rstrip().endswith("Question: What is it?"))


class AnswerQuestionTests(unittest.TestCase):
    def test_grounded_answer_returns_answer_plus_source_metadata_only(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = [make_chunk("doc.txt-0", "Alpha text")]
        llm = MagicMock()
        llm.generate.return_value = "Grounded answer."

        result = answer_question("q", retriever, llm)

        self.assertEqual(result["answer"], "Grounded answer.")
        self.assertEqual(
            result["sources"],
            [{"filename": "doc.txt", "chunk_id": "doc.txt-0", "similarity": 0.8}],
        )
        # Full chunk text must NOT leak into the sources payload.
        self.assertNotIn("chunk_text", result["sources"][0])
        llm.generate.assert_called_once()

    def test_empty_retrieval_skips_the_llm_and_returns_the_honest_fallback(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = []
        llm = MagicMock()

        result = answer_question("q", retriever, llm)

        self.assertEqual(result["sources"], [])
        self.assertIn("don't know", result["answer"])
        llm.generate.assert_not_called()


class AnswerQuestionStreamTests(unittest.TestCase):
    def test_emits_sources_first_then_token_events(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = [make_chunk("doc.txt-0", "Alpha")]
        llm = MagicMock()
        llm.generate_stream.return_value = iter(["Hel", "lo"])

        events = list(answer_question_stream("q", retriever, llm))

        self.assertEqual(events[0]["type"], "sources")
        self.assertEqual(events[0]["sources"][0]["chunk_id"], "doc.txt-0")
        self.assertNotIn("chunk_text", events[0]["sources"][0])
        self.assertEqual(
            [e["text"] for e in events if e["type"] == "token"], ["Hel", "lo"]
        )

    def test_empty_retrieval_streams_the_fallback_and_never_calls_the_llm(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = []
        llm = MagicMock()

        events = list(answer_question_stream("q", retriever, llm))

        self.assertEqual(events[0]["type"], "sources")
        self.assertEqual(events[0]["sources"], [])
        self.assertTrue(any("don't know" in e.get("text", "") for e in events))
        llm.generate_stream.assert_not_called()


class LLMTests(unittest.TestCase):
    @patch("llm.requests.post")
    def test_generate_stream_yields_content_deltas_and_stops_on_done(self, post):
        lines = [
            json.dumps({"message": {"content": "Hel"}}).encode(),
            json.dumps({"message": {"content": "lo"}}).encode(),
            b"",  # keep-alive blank line — must be skipped, not parsed
            json.dumps({"message": {"content": ""}, "done": True}).encode(),
            # Anything after done must never be yielded (loop breaks).
            json.dumps({"message": {"content": "LEAKED"}}).encode(),
        ]
        response = MagicMock()
        response.iter_lines.return_value = iter(lines)
        post.return_value = response

        out = list(LLM().generate_stream("system", "user"))

        self.assertEqual(out, ["Hel", "lo"])
        # The upstream connection is always closed (frees Ollama's CPU).
        response.close.assert_called_once()

    @patch("llm.requests.post")
    def test_generate_returns_the_message_content(self, post):
        response = MagicMock()
        response.json.return_value = {"message": {"content": "Answer."}}
        post.return_value = response

        self.assertEqual(LLM().generate("system", "user"), "Answer.")
        response.raise_for_status.assert_called_once()


class EnrichSourcesTests(unittest.TestCase):
    def _service(self) -> RagService:
        # Bypass __init__ (which loads the embedding model + opens Chroma);
        # we only exercise the pure enrichment logic with a mock handle.
        service = RagService.__new__(RagService)
        service.retriever = MagicMock()
        return service

    def test_attaches_a_truncated_preview_with_an_ellipsis(self):
        service = self._service()
        long_text = "x" * (PREVIEW_CHARS + 50)
        service.retriever.collection.get.return_value = {
            "ids": ["doc.txt-0"],
            "documents": [long_text],
        }
        sources = [{"filename": "doc.txt", "chunk_id": "doc.txt-0", "similarity": 0.8}]

        service._enrich_sources(sources)

        self.assertTrue(sources[0]["preview"].endswith("…"))
        self.assertEqual(len(sources[0]["preview"]), PREVIEW_CHARS + 1)

    def test_short_text_is_not_truncated(self):
        service = self._service()
        service.retriever.collection.get.return_value = {
            "ids": ["doc.txt-0"],
            "documents": ["short"],
        }
        sources = [{"filename": "doc.txt", "chunk_id": "doc.txt-0", "similarity": 0.8}]

        service._enrich_sources(sources)

        self.assertEqual(sources[0]["preview"], "short")

    def test_no_sources_makes_no_database_call(self):
        service = self._service()
        service._enrich_sources([])
        service.retriever.collection.get.assert_not_called()


class ChunkDocumentsTests(unittest.TestCase):
    def test_chunk_ids_encode_the_filename_and_ordinal_position(self):
        docs = [{"filename": "doc.txt", "text": "word " * 800}]

        chunks = chunk_documents(docs)

        self.assertGreater(len(chunks), 1)  # long text splits into several
        self.assertEqual(chunks[0]["chunk_id"], "doc.txt-0")
        self.assertEqual(chunks[1]["chunk_id"], "doc.txt-1")
        for chunk in chunks:
            self.assertEqual(chunk["filename"], "doc.txt")
            self.assertTrue(chunk["chunk_text"].strip())


if __name__ == "__main__":
    unittest.main(verbosity=2)
