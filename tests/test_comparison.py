# tests/test_comparison.py
#
# Automated regression unit and API test suite for ContextIQ 2.0 Phase C3:
# Document Comparison. Mocks expensive LLM calls so tests execute quickly.

import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from comparison_service import ComparisonService, _parse_comparison_json


class ComparisonServiceUnitTests(unittest.TestCase):
    def test_json_parsing_robustness(self):
        """Verify robust parsing for clean JSON, markdown blocks, and bullet fallbacks."""
        filenames = ["doc_a.pdf", "doc_b.pdf"]

        # 1. Clean JSON
        raw1 = json.dumps({
            "summary": "Both reports discuss annual financial metrics.",
            "similarities": ["Revenue increased in both."],
            "differences": ["Operating costs rose in 2025."],
            "document_a_only": ["2024 tax rebate details."],
            "document_b_only": ["2025 expansion plans."],
        })
        parsed1 = _parse_comparison_json(raw1, filenames)
        self.assertEqual(parsed1["summary"], "Both reports discuss annual financial metrics.")
        self.assertEqual(parsed1["similarities"], ["Revenue increased in both."])
        self.assertEqual(parsed1["differences"], ["Operating costs rose in 2025."])

        # 2. Markdown fenced JSON
        raw2 = f"```json\n{raw1}\n```"
        parsed2 = _parse_comparison_json(raw2, filenames)
        self.assertEqual(parsed2["summary"], "Both reports discuss annual financial metrics.")

        # 3. Fallback text parsing
        raw3 = "Overview paragraph.\n- Both documents discuss safety policies.\n- However, doc_b introduces new compliance standards."
        parsed3 = _parse_comparison_json(raw3, filenames)
        self.assertTrue(len(parsed3["similarities"]) > 0 or len(parsed3["differences"]) > 0)

    @patch("comparison_service.MetadataStore")
    @patch("api.services.rag_service.RagService._enrich_sources")
    def test_compare_documents_success(self, mock_enrich, mock_metadata_store):
        """Verify end-to-end comparison with mocked retriever and LLM."""
        mock_metadata_store.get_document_meta.side_effect = lambda fname: {"filename": fname}

        mock_retriever = MagicMock()
        mock_retriever.retrieve.side_effect = lambda query, top_k, document_filter, collection_id: [
            {
                "filename": document_filter,
                "chunk_id": f"{document_filter}-0",
                "similarity": 0.85,
                "chunk_text": f"Sample chunk for {document_filter}",
            }
        ]

        mock_llm = MagicMock()
        mock_llm.generate.return_value = json.dumps({
            "summary": "Comparative summary.",
            "similarities": ["Shared point 1"],
            "differences": ["Difference 1"],
            "document_a_only": ["A exclusive"],
            "document_b_only": ["B exclusive"],
        })

        service = ComparisonService(retriever=mock_retriever, llm=mock_llm)
        res = service.compare_documents(
            filenames=["report_2024.pdf", "report_2025.pdf"],
            question="Compare risks",
        )

        self.assertEqual(res["filenames"], ["report_2024.pdf", "report_2025.pdf"])
        self.assertEqual(res["summary"], "Comparative summary.")
        self.assertEqual(res["similarities"], ["Shared point 1"])
        self.assertEqual(res["differences"], ["Difference 1"])
        self.assertEqual(len(res["sources"]), 2)

    @patch("comparison_service.MetadataStore")
    def test_compare_documents_missing_document(self, mock_metadata_store):
        """Verify ValueError raised when a requested document does not exist."""
        mock_metadata_store.get_document_meta.return_value = None

        service = ComparisonService(retriever=MagicMock(), llm=MagicMock())
        with self.assertRaises(ValueError):
            service.compare_documents(["nonexistent.pdf", "valid.pdf"])

    @patch("comparison_service.MetadataStore")
    def test_compare_documents_collection_scope_isolation(self, mock_metadata_store):
        """Verify PermissionError raised when a document is outside active collection."""
        # Collection A only contains doc_a.pdf
        mock_metadata_store.list_documents.return_value = [{"filename": "doc_a.pdf"}]

        service = ComparisonService(retriever=MagicMock(), llm=MagicMock())
        with self.assertRaises(PermissionError):
            service.compare_documents(
                filenames=["doc_a.pdf", "doc_b.pdf"],
                collection_id="collection_a_id",
            )


class ComparisonApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("api.routers.compare.ComparisonService.compare_documents")
    def test_compare_api_endpoint_success(self, mock_compare):
        mock_compare.return_value = {
            "filenames": ["doc_a.pdf", "doc_b.pdf"],
            "question": "Compare major risks.",
            "summary": "Summary text.",
            "similarities": ["Sim 1"],
            "differences": ["Diff 1"],
            "document_a_only": [],
            "document_b_only": [],
            "sources": [],
        }

        res = self.client.post(
            "/compare",
            json={
                "filenames": ["doc_a.pdf", "doc_b.pdf"],
                "question": "Compare major risks.",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["filenames"], ["doc_a.pdf", "doc_b.pdf"])
        self.assertEqual(data["summary"], "Summary text.")

    def test_compare_api_validation_min_documents(self):
        """Verify 422 status code when fewer than 2 documents are provided."""
        res = self.client.post(
            "/compare",
            json={"filenames": ["single_doc.pdf"]},
        )
        self.assertEqual(res.status_code, 422)

    def test_compare_api_validation_max_documents(self):
        """Verify 422 status code when more than 5 documents are provided."""
        res = self.client.post(
            "/compare",
            json={
                "filenames": [
                    "d1.pdf",
                    "d2.pdf",
                    "d3.pdf",
                    "d4.pdf",
                    "d5.pdf",
                    "d6.pdf",
                ]
            },
        )
        self.assertEqual(res.status_code, 422)


if __name__ == "__main__":
    unittest.main()
