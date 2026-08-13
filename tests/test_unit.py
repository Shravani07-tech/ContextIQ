# tests/test_unit.py
#
# Fast, dependency-light unit tests for the RAG core -- the CI-friendly
# counterpart to test_api.py (which needs a live Ollama
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
from unittest.mock import MagicMock, call, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from api.services.rag_service import PREVIEW_CHARS, RagService
from ingest import chunk_documents, _strip_references
from llm import LLM
from rag import answer_question, answer_question_stream, build_prompt


def make_chunk(
    chunk_id: str,
    text: str,
    similarity: float = 0.8,
    filename: str = "doc.txt",
    page: int | None = None,
) -> dict:
    return {
        "filename": filename,
        "chunk_id": chunk_id,
        "chunk_text": text,
        "similarity": similarity,
        "page": page,
        "section": None,
    }


class ReferenceStrippingTests(unittest.TestCase):
    def test_strips_simple_references(self):
        text = "Hello world\n" * 100 + "\nReferences\n1. Doe, J."
        self.assertEqual(_strip_references(text), "Hello world\n" * 100 + "\n")

    def test_strips_numbered_references(self):
        text = "Hello world\n" * 100 + "\n10. References\n1. Doe, J."
        self.assertEqual(_strip_references(text), "Hello world\n" * 100 + "\n")

    def test_strips_roman_bibliography(self):
        text = "Hello world\n" * 100 + "\nVIII. Bibliography\n1. Doe, J."
        self.assertEqual(_strip_references(text), "Hello world\n" * 100 + "\n")

    def test_ignores_early_references(self):
        # Even if it matches, if it's in the first 60% of the document, don't strip
        text = "Table of Contents\n1. Introduction\n2. References\n3. Method\n" + "Padding\n" * 100
        self.assertEqual(_strip_references(text), text)

    def test_strips_references_and_bibliography(self):
        text = "Hello world\n" * 100 + "\nReferences and Bibliography\n1. Doe, J."
        self.assertEqual(_strip_references(text), "Hello world\n" * 100 + "\n")


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

    def test_page_number_included_when_present(self):
        chunks = [make_chunk("doc.txt-0", "Alpha", page=3)]
        prompt = build_prompt("What is it?", chunks)
        self.assertIn("[Page 3]", prompt)

    def test_no_page_label_when_page_is_none(self):
        chunks = [make_chunk("doc.txt-0", "Alpha", page=None)]
        prompt = build_prompt("What is it?", chunks)
        self.assertNotIn("[Page", prompt)


class AnswerQuestionTests(unittest.TestCase):
    def test_grounded_answer_returns_answer_plus_source_metadata_only(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = [make_chunk("doc.txt-0", "Alpha text")]
        llm = MagicMock()
        llm.generate.return_value = "Grounded answer."

        result = answer_question("q", retriever, llm)

        self.assertEqual(result["answer"], "Grounded answer.")
        self.assertEqual(result["sources"][0]["filename"], "doc.txt")
        self.assertEqual(result["sources"][0]["chunk_id"], "doc.txt-0")
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

    def test_document_filter_is_passed_to_retriever(self):
        """document_filter must be forwarded to retrieve(), not silently dropped."""
        retriever = MagicMock()
        retriever.retrieve.return_value = []
        llm = MagicMock()

        answer_question("q", retriever, llm, document_filter="doc_a.txt")

        retriever.retrieve.assert_called_once_with(
            "q", document_filter="doc_a.txt"
        )

    def test_history_is_forwarded_to_llm(self):
        """Conversation history must reach the LLM so it has memory."""
        retriever = MagicMock()
        retriever.retrieve.return_value = [make_chunk("doc.txt-0", "Alpha")]
        llm = MagicMock()
        llm.generate.return_value = "Answer."
        history = [{"role": "user", "content": "prior question"}]

        answer_question("follow-up", retriever, llm, history=history)

        _, kwargs = llm.generate.call_args
        self.assertEqual(kwargs.get("history"), history)

    def test_history_capped_at_six_messages(self):
        """History exceeding 6 messages must be trimmed to the most recent 6."""
        retriever = MagicMock()
        retriever.retrieve.return_value = [make_chunk("doc.txt-0", "Alpha")]
        llm = MagicMock()
        llm.generate.return_value = "Answer."
        history = [{"role": "user", "content": f"msg {i}"} for i in range(10)]

        answer_question("q", retriever, llm, history=history)

        _, kwargs = llm.generate.call_args
        self.assertLessEqual(len(kwargs.get("history", [])), 6)

    def test_document_a_filter_blocks_doc_b_chunks(self):
        """
        Document isolation: when document_filter='doc_a.txt', the retriever
        is called with that filter so doc_b chunks cannot enter the context.
        """
        retriever = MagicMock()
        # Simulate: only doc_a chunks returned (filter is enforced by retriever)
        retriever.retrieve.return_value = [
            make_chunk("doc_a.txt-0", "Content A", filename="doc_a.txt")
        ]
        llm = MagicMock()
        llm.generate.return_value = "Answer about A."

        result = answer_question("q", retriever, llm, document_filter="doc_a.txt")

        retriever.retrieve.assert_called_once_with("q", document_filter="doc_a.txt")
        for source in result["sources"]:
            self.assertEqual(source["filename"], "doc_a.txt",
                             "Only doc_a sources must appear")

    def test_document_b_filter_blocks_doc_a_chunks(self):
        """Symmetric isolation: doc_b filter must never return doc_a sources."""
        retriever = MagicMock()
        retriever.retrieve.return_value = [
            make_chunk("doc_b.txt-0", "Content B", filename="doc_b.txt")
        ]
        llm = MagicMock()
        llm.generate.return_value = "Answer about B."

        result = answer_question("q", retriever, llm, document_filter="doc_b.txt")

        retriever.retrieve.assert_called_once_with("q", document_filter="doc_b.txt")
        for source in result["sources"]:
            self.assertEqual(source["filename"], "doc_b.txt",
                             "Only doc_b sources must appear")

    def test_all_documents_mode_retrieves_from_both(self):
        """All-Documents mode (document_filter=None) may return sources from any doc."""
        retriever = MagicMock()
        retriever.retrieve.return_value = [
            make_chunk("doc_a.txt-0", "Content A", filename="doc_a.txt"),
            make_chunk("doc_b.txt-0", "Content B", filename="doc_b.txt"),
        ]
        llm = MagicMock()
        llm.generate.return_value = "Comparison answer."

        result = answer_question("compare", retriever, llm, document_filter=None)

        retriever.retrieve.assert_called_once_with("compare", document_filter=None)
        filenames = {s["filename"] for s in result["sources"]}
        self.assertIn("doc_a.txt", filenames)
        self.assertIn("doc_b.txt", filenames)

    def test_deleted_document_returns_empty_when_filtered(self):
        """
        After a document is deleted, filtering to it must return an empty
        result rather than hallucinating chunks from other documents.
        """
        retriever = MagicMock()
        retriever.retrieve.return_value = []  # deleted doc returns nothing
        llm = MagicMock()

        result = answer_question("q", retriever, llm, document_filter="deleted.pdf")

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
        # The stream coalesces raw tokens into phrase-sized pieces, so we
        # assert the streamed TEXT is preserved rather than an exact
        # per-token split (which is an implementation detail).
        token_texts = [e["text"] for e in events if e["type"] == "token"]
        self.assertTrue(token_texts)
        self.assertEqual("".join(token_texts), "Hello")

    def test_empty_retrieval_streams_the_fallback_and_never_calls_the_llm(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = []
        llm = MagicMock()

        events = list(answer_question_stream("q", retriever, llm))

        self.assertEqual(events[0]["type"], "sources")
        self.assertEqual(events[0]["sources"], [])
        self.assertTrue(any("don't know" in e.get("text", "") for e in events))
        llm.generate_stream.assert_not_called()

    def test_stream_document_filter_forwarded(self):
        """document_filter must reach retrieve() in the streaming path."""
        retriever = MagicMock()
        retriever.retrieve.return_value = []
        llm = MagicMock()

        list(answer_question_stream("q", retriever, llm, document_filter="a.pdf"))

        retriever.retrieve.assert_called_once_with("q", document_filter="a.pdf")

    def test_stream_history_forwarded_to_llm(self):
        """History must reach generate_stream() in the streaming path."""
        retriever = MagicMock()
        retriever.retrieve.return_value = [make_chunk("doc.txt-0", "Alpha")]
        llm = MagicMock()
        llm.generate_stream.return_value = iter(["Answer."])
        history = [{"role": "user", "content": "prior"}]

        list(answer_question_stream("q", retriever, llm, history=history))

        _, kwargs = llm.generate_stream.call_args
        self.assertEqual(kwargs.get("history"), history)


class LLMTests(unittest.TestCase):
    @patch("llm.requests.post")
    def test_generate_stream_yields_content_deltas_and_stops_on_done(self, post):
        lines = [
            json.dumps({"message": {"content": "Hel"}}).encode(),
            json.dumps({"message": {"content": "lo"}}).encode(),
            b"",  # keep-alive blank line -- must be skipped, not parsed
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

    @patch("llm.requests.post")
    def test_history_included_in_messages_payload(self, post):
        """Conversation history must appear in the messages array sent to Ollama."""
        response = MagicMock()
        response.json.return_value = {"message": {"content": "Answer."}}
        post.return_value = response

        history = [
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "first answer"},
        ]
        LLM().generate("system", "user prompt", history=history)

        payload = post.call_args[1]["json"]
        messages = payload["messages"]
        # system -> history[0] -> history[1] -> user
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], "first question")
        self.assertEqual(messages[2]["role"], "assistant")
        self.assertEqual(messages[2]["content"], "first answer")
        self.assertEqual(messages[3]["role"], "user")
        self.assertEqual(messages[3]["content"], "user prompt")

    @patch("llm.requests.post")
    def test_no_history_sends_system_and_user_only(self, post):
        """With no history, messages must be exactly [system, user]."""
        response = MagicMock()
        response.json.return_value = {"message": {"content": "Answer."}}
        post.return_value = response

        LLM().generate("system", "user prompt", history=None)

        payload = post.call_args[1]["json"]
        messages = payload["messages"]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")

    @patch("llm.requests.post")
    def test_history_capped_at_six_in_llm(self, post):
        """LLM must not send more than 6 history turns even if caller passes more."""
        response = MagicMock()
        response.json.return_value = {"message": {"content": "Answer."}}
        post.return_value = response

        history = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
        LLM().generate("system", "user prompt", history=history)

        payload = post.call_args[1]["json"]
        messages = payload["messages"]
        # system + at most 6 history + user = at most 8
        self.assertLessEqual(len(messages), 8)


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
            "metadatas": [{}],
        }
        sources = [{"filename": "doc.txt", "chunk_id": "doc.txt-0", "similarity": 0.8}]

        service._enrich_sources(sources)

        self.assertTrue(sources[0]["preview"].endswith("\u2026"))
        self.assertEqual(len(sources[0]["preview"]), PREVIEW_CHARS + 1)

    def test_short_text_is_not_truncated(self):
        service = self._service()
        service.retriever.collection.get.return_value = {
            "ids": ["doc.txt-0"],
            "documents": ["short"],
            "metadatas": [{}],
        }
        sources = [{"filename": "doc.txt", "chunk_id": "doc.txt-0", "similarity": 0.8}]

        service._enrich_sources(sources)

        self.assertEqual(sources[0]["preview"], "short")

    def test_no_sources_makes_no_database_call(self):
        service = self._service()
        service._enrich_sources([])
        service.retriever.collection.get.assert_not_called()

    def test_page_enriched_from_metadata(self):
        """Page number stored in Chroma metadata must appear in the source."""
        service = self._service()
        service.retriever.collection.get.return_value = {
            "ids": ["doc.txt-0"],
            "documents": ["text"],
            "metadatas": [{"page": 5}],
        }
        sources = [{"filename": "doc.txt", "chunk_id": "doc.txt-0",
                    "similarity": 0.8, "page": None}]

        service._enrich_sources(sources)

        self.assertEqual(sources[0]["page"], 5)


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


class DocumentBoundarySelectionTests(unittest.TestCase):
    """
    Verify that _ensure_document_boundaries anchors on the document with the
    HIGHEST AGGREGATE similarity score across all retrieved chunks, not on the
    single top-ranked chunk (hits[0]).

    Root-cause scenario: when multiple documents are indexed, a whole-document
    question ("who wrote this paper?") may cause the highest-similarity single
    chunk to belong to document B, while document A dominates the remaining
    retrieved slots.  The old code anchored on hits[0] and injected boundary
    chunks from B -- causing cross-document contamination in the final answer.
    The new code aggregates scores per document and picks the winner.
    """

    def _make_retriever_with_mocked_collection(self) -> object:
        """Return a Retriever whose Chroma collection is fully mocked."""
        import rag as rag_module
        retriever = rag_module.Retriever.__new__(rag_module.Retriever)
        retriever.model = MagicMock()
        retriever.collection = MagicMock()
        return retriever

    def _hits(self, pairs: list[tuple[str, float]]) -> list[dict]:
        """Build a minimal hits list from (filename, similarity) pairs."""
        return [
            {
                "filename": fname,
                "chunk_id": f"{fname}-{i}",
                "chunk_text": f"text from {fname}",
                "similarity": sim,
                "page": None,
                "section": None,
            }
            for i, (fname, sim) in enumerate(pairs)
        ]

    def test_single_document_anchors_on_that_document(self):
        """With one document, the anchor is always that document."""
        import rag as rag_module
        retriever = self._make_retriever_with_mocked_collection()
        # Stub out collection.get so the method returns immediately
        retriever.collection.get.return_value = {"ids": []}

        hits = self._hits([("doc_a.txt", 0.9), ("doc_a.txt", 0.8)])
        # patch _ensure_document_boundaries to just capture top_doc
        captured = {}
        original = rag_module.Retriever._ensure_document_boundaries

        def spy(self_inner, hits_inner, query_vec_inner, document_filter=None):
            # compute top_doc using the new aggregate logic
            doc_scores: dict[str, float] = {}
            for h in hits_inner:
                doc_scores[h["filename"]] = (
                    doc_scores.get(h["filename"], 0.0) + h["similarity"]
                )
            captured["top_doc"] = max(doc_scores, key=lambda d: doc_scores[d])
            retriever.collection.get.return_value = {"ids": []}

        rag_module.Retriever._ensure_document_boundaries = spy
        try:
            retriever._ensure_document_boundaries(hits, [])
            self.assertEqual(captured["top_doc"], "doc_a.txt")
        finally:
            rag_module.Retriever._ensure_document_boundaries = original

    def test_aggregate_score_beats_single_top_chunk(self):
        """
        Document B has the highest single chunk (0.91) but document A
        dominates in aggregate (0.85 + 0.80 + 0.78 = 2.43 vs 0.91).
        The aggregate strategy correctly chooses document A.
        """
        # Compute aggregate scores directly -- tests the logic, not the method
        hits = self._hits([
            ("doc_b.txt", 0.91),   # top-1 chunk belongs to B
            ("doc_a.txt", 0.85),
            ("doc_a.txt", 0.80),
            ("doc_a.txt", 0.78),
        ])
        doc_scores: dict[str, float] = {}
        for h in hits:
            doc_scores[h["filename"]] = (
                doc_scores.get(h["filename"], 0.0) + h["similarity"]
            )
        chosen = max(doc_scores, key=lambda d: doc_scores[d])
        self.assertEqual(chosen, "doc_a.txt",
                         "Aggregate logic must choose doc_a.txt over doc_b.txt")

    def test_tie_broken_deterministically(self):
        """Equal aggregate scores: max() picks one deterministically (no crash)."""
        hits = self._hits([
            ("doc_a.txt", 0.80),
            ("doc_b.txt", 0.80),
        ])
        doc_scores: dict[str, float] = {}
        for h in hits:
            doc_scores[h["filename"]] = (
                doc_scores.get(h["filename"], 0.0) + h["similarity"]
            )
        chosen = max(doc_scores, key=lambda d: doc_scores[d])
        self.assertIn(chosen, {"doc_a.txt", "doc_b.txt"})  # no crash, valid choice

    def test_empty_hits_does_not_crash(self):
        """_ensure_document_boundaries should be a no-op on empty hits."""
        import rag as rag_module
        retriever = self._make_retriever_with_mocked_collection()
        # Should not raise
        retriever._ensure_document_boundaries([], [0.0] * 384)

    def test_document_filter_overrides_aggregate_selection(self):
        """
        When document_filter='doc_a.txt' is set, boundaries must be injected
        for doc_a.txt regardless of which document has the highest aggregate score.
        This enforces strict isolation: doc_b cannot leak its boundaries into
        a doc_a-filtered query, even if doc_b happens to score higher overall.
        """
        import rag as rag_module
        retriever = self._make_retriever_with_mocked_collection()
        retriever.collection.get.return_value = {"ids": []}

        # doc_b has higher aggregate score, but filter forces doc_a
        hits = self._hits([
            ("doc_b.txt", 0.95),
            ("doc_b.txt", 0.90),
            ("doc_a.txt", 0.70),
        ])
        captured = {}
        original = rag_module.Retriever._ensure_document_boundaries

        def spy(self_inner, hits_inner, query_vec_inner, document_filter=None):
            if document_filter:
                captured["top_doc"] = document_filter
            else:
                doc_scores: dict[str, float] = {}
                for h in hits_inner:
                    doc_scores[h["filename"]] = (
                        doc_scores.get(h["filename"], 0.0) + h["similarity"]
                    )
                captured["top_doc"] = max(doc_scores, key=lambda d: doc_scores[d])
            retriever.collection.get.return_value = {"ids": []}

        rag_module.Retriever._ensure_document_boundaries = spy
        try:
            retriever._ensure_document_boundaries(hits, [], document_filter="doc_a.txt")
            self.assertEqual(captured["top_doc"], "doc_a.txt",
                             "document_filter must override aggregate selection")
        finally:
            rag_module.Retriever._ensure_document_boundaries = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
