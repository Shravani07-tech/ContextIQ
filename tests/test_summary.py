# tests/test_summary.py
#
# Automated regression unit and API test suite for ContextIQ 2.0 Phase C1:
# Automatic Document Summarization. Mocks the LLM layer so tests run fast.

import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from metadata_store import MetadataStore
from summary_service import SummaryService


class SummaryServiceUnitTests(unittest.TestCase):
    def setUp(self):
        import os
        from config import DATA_DIR
        # Clean test state for document summary
        self.filename = "test_summary_doc.txt"
        self.file_path = os.path.join(DATA_DIR, self.filename)
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write("Sample test document content for summarization unit test.")
        MetadataStore.upsert_document(filename=self.filename, file_type="txt", file_size=500, chunk_count=2)
        MetadataStore.delete_summary(self.filename)

    def tearDown(self):
        import os
        MetadataStore.delete_summary(self.filename)
        MetadataStore.delete_document_meta(self.filename)
        if os.path.exists(self.file_path):
            os.remove(self.file_path)


    def test_summary_persistence_crud(self):
        """Verify summary persistence in SQLite metadata_store."""
        saved = MetadataStore.save_summary(
            filename=self.filename,
            summary="This is a test summary.",
            key_points=["Point 1", "Point 2"],
            status="completed",
        )
        self.assertEqual(saved["filename"], self.filename)
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(saved["summary"], "This is a test summary.")
        self.assertEqual(saved["key_points"], ["Point 1", "Point 2"])

        fetched = MetadataStore.get_summary(self.filename)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["summary"], "This is a test summary.")

        # Update status
        updated = MetadataStore.update_summary_status(self.filename, status="failed", error="Ollama timeout")
        self.assertEqual(updated["status"], "failed")
        self.assertEqual(updated["error"], "Ollama timeout")

        # Delete summary
        deleted = MetadataStore.delete_summary(self.filename)
        self.assertTrue(deleted)
        self.assertIsNone(MetadataStore.get_summary(self.filename))

    def test_json_parsing_and_fallback(self):
        """Verify robust JSON parsing for raw JSON, markdown blocks, and fallback."""
        svc = SummaryService(llm=MagicMock())

        # Valid JSON string
        res1 = svc._parse_llm_json('{"summary": "Overview paragraph.", "key_points": ["Key 1", "Key 2"]}')
        self.assertEqual(res1["summary"], "Overview paragraph.")
        self.assertEqual(res1["key_points"], ["Key 1", "Key 2"])

        # Markdown wrapped JSON
        res2 = svc._parse_llm_json('```json\n{"summary": "Markdown overview.", "key_points": ["Point A"]}\n```')
        self.assertEqual(res2["summary"], "Markdown overview.")
        self.assertEqual(res2["key_points"], ["Point A"])

        # Non-JSON fallback text
        res3 = svc._parse_llm_json("Plain summary text.\n- Bullet point 1\n- Bullet point 2")
        self.assertTrue("Plain summary text." in res3["summary"])
        self.assertIn("Bullet point 1", res3["key_points"])

    @patch("summary_service.default_registry")
    def test_summarize_document_success(self, mock_registry):
        """Verify small document summarization pipeline using mocked LLM."""
        mock_parser = MagicMock()
        mock_norm = MagicMock()
        mock_norm.text = "ContextIQ provides private AI document intelligence with hybrid retrieval."
        mock_norm.file_type = "txt"
        mock_norm.extraction_method = "text"
        mock_parser.parse.return_value = mock_norm
        mock_registry.get_parser.return_value = mock_parser

        mock_llm = MagicMock()
        mock_llm.generate.return_value = json.dumps({
            "summary": "ContextIQ is a private AI system.",
            "key_points": ["Private AI", "Hybrid Retrieval"]
        })

        svc = SummaryService(llm=mock_llm)
        res = svc.summarize_document(self.filename, force=True)

        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["summary"], "ContextIQ is a private AI system.")
        self.assertEqual(res["key_points"], ["Private AI", "Hybrid Retrieval"])

    @patch("summary_service.default_registry")
    def test_summarize_document_failure_isolation(self, mock_registry):
        """Verify failure isolation: LLM exception records status='failed' without crashing."""
        mock_parser = MagicMock()
        mock_norm = MagicMock()
        mock_norm.text = "Sample text."
        mock_norm.file_type = "txt"
        mock_norm.extraction_method = "text"
        mock_parser.parse.return_value = mock_norm
        mock_registry.get_parser.return_value = mock_parser

        mock_llm = MagicMock()
        mock_llm.generate.side_effect = RuntimeError("Ollama service unavailable")

        svc = SummaryService(llm=mock_llm)
        res = svc.summarize_document(self.filename, force=True)

        self.assertEqual(res["status"], "failed")
        self.assertIn("Ollama service unavailable", res["error"])

    def test_large_document_text_sampling(self):
        """Verify large document sampling limits input text length."""
        svc = SummaryService(llm=MagicMock())
        huge_text = "A" * 30000
        sampled = svc._sample_large_text(huge_text)
        self.assertLess(len(sampled), 30000)
        self.assertIn("middle section excerpt", sampled)


class SummaryApiTests(unittest.TestCase):
    def setUp(self):
        import os
        from config import DATA_DIR
        self.client = TestClient(app)
        self.filename = "api_summary_test.txt"
        self.file_path = os.path.join(DATA_DIR, self.filename)
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write("Sample content for API summary test.")
        MetadataStore.upsert_document(filename=self.filename, file_type="txt", file_size=100, chunk_count=1)
        MetadataStore.save_summary(
            filename=self.filename,
            summary="API test summary.",
            key_points=["API Point 1"],
            status="completed",
        )

    def tearDown(self):
        import os
        MetadataStore.delete_summary(self.filename)
        MetadataStore.delete_document_meta(self.filename)
        if os.path.exists(self.file_path):
            os.remove(self.file_path)


    def test_get_document_summary(self):
        """GET /documents/{filename}/summary returns stored summary."""
        res = self.client.get(f"/documents/{self.filename}/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["filename"], self.filename)
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["summary"], "API test summary.")

    def test_get_summary_unknown_file(self):
        """GET /documents/unknown.txt/summary returns 404."""
        res = self.client.get("/documents/unknown.txt/summary")
        self.assertEqual(res.status_code, 404)

    @patch("api.routers.documents.get_stored_filenames")
    @patch("summary_service.SummaryService.summarize_document")
    def test_retry_document_summary(self, mock_summarize, mock_stored_filenames):
        """POST /documents/{filename}/summary/retry forces re-summarization."""
        mock_stored_filenames.return_value = [self.filename]
        mock_summarize.return_value = {
            "document_id": self.filename,
            "filename": self.filename,
            "status": "completed",
            "summary": "Retried summary.",
            "key_points": ["Retried point"],
            "version": 2,
        }

        res = self.client.post(f"/documents/{self.filename}/summary/retry")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["summary"], "Retried summary.")


if __name__ == "__main__":
    unittest.main()
