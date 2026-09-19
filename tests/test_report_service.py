# tests/test_report_service.py
#
# Unit and integration test suite for ContextIQ 2.0 Phase C6: Exportable Research Reports.
# Tests Markdown, PDF, and Plain Text report generation, attribution preservation,
# verification & contradiction metadata inclusion, and export API response headers.

import unittest
from fastapi.testclient import TestClient

from api.main import app
from report_service import ResearchReportService


class ResearchReportUnitTest(unittest.TestCase):
    def setUp(self):
        self.svc = ResearchReportService()
        self.sample_payload = {
            "question": "What are the major findings and risks?",
            "answer": "The report highlights supply chain disruptions and revenue growth.",
            "sources": [
                {
                    "filename": "Financial_Report_2025.pdf",
                    "chunk_id": "doc1-14",
                    "similarity": 0.92,
                    "page": 14,
                    "section": "Risk Factors",
                    "preview": "Supply chain disruption poses a significant Q3 risk."
                }
            ],
            "doc_count": 1,
            "citation_verification": [
                {
                    "claim": "Supply chain disruption is a major risk.",
                    "status": "SUPPORTED",
                    "citation_ids": ["doc1-14"],
                    "reason": "Explicitly confirmed in source text."
                }
            ],
            "contradictions": [
                {
                    "topic": "Revenue Growth Target",
                    "status": "CONTRADICTION",
                    "claim_a": "Revenue predicted to grow 25%.",
                    "claim_b": "Revenue predicted to grow 35%.",
                    "source_a": "Financial_Report_2025.pdf",
                    "source_b": "Investor_Deck.pptx",
                    "severity": "HIGH",
                    "reason": "Conflicting percentage projections for 2025."
                }
            ],
            "collection_name": "Q3 Research",
            "document_filter": None,
            "generated_at": "2026-09-19 20:00:00 UTC",
        }

    def test_markdown_report_generation(self):
        md = self.svc.generate_markdown(self.sample_payload)

        self.assertIn("# ContextIQ Research Report", md)
        self.assertIn("What are the major findings and risks?", md)
        self.assertIn("The report highlights supply chain disruptions", md)
        self.assertIn("Financial_Report_2025.pdf", md)
        self.assertIn("(Page 14)", md)
        self.assertIn("SUPPORTED", md)
        self.assertIn("Revenue Growth Target", md)

    def test_txt_report_generation(self):
        txt = self.svc.generate_txt(self.sample_payload)

        self.assertIn("ContextIQ Research Report", txt)
        self.assertIn("Executive Summary & Findings", txt)
        self.assertIn("Financial_Report_2025.pdf", txt)
        self.assertNotIn("```", txt)
        self.assertNotIn("**", txt)

    def test_pdf_report_generation(self):
        pdf_bytes = self.svc.generate_pdf(self.sample_payload)

        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(len(pdf_bytes) > 500)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_empty_optional_fields_handled_cleanly(self):
        empty_payload = {
            "question": "Simple Query",
            "answer": "Simple Answer.",
            "sources": [],
        }

        md = self.svc.generate_markdown(empty_payload)
        pdf_bytes = self.svc.generate_pdf(empty_payload)

        self.assertIn("Simple Query", md)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))


class ResearchReportApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.payload = {
            "format": "markdown",
            "question": "What is Zephyra?",
            "answer": "Zephyra is a privacy-first AI architecture.",
            "sources": [
                {
                    "filename": "zephyra.txt",
                    "chunk_id": "zephyra.txt-1",
                    "similarity": 0.88,
                    "preview": "Zephyra is a privacy-first AI architecture."
                }
            ],
            "doc_count": 1,
        }

    def test_export_markdown_api_headers(self):
        resp = self.client.post("/research/export", json={**self.payload, "format": "markdown"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/markdown", resp.headers["content-type"])
        self.assertIn("attachment; filename=\"contextiq-research-report.md\"", resp.headers["content-disposition"])
        self.assertIn("# ContextIQ Research Report", resp.text)

    def test_export_pdf_api_headers(self):
        resp = self.client.post("/research/export", json={**self.payload, "format": "pdf"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/pdf", resp.headers["content-type"])
        self.assertIn("attachment; filename=\"contextiq-research-report.pdf\"", resp.headers["content-disposition"])
        self.assertTrue(resp.content.startswith(b"%PDF"))

    def test_export_txt_api_headers(self):
        resp = self.client.post("/research/export", json={**self.payload, "format": "txt"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/plain", resp.headers["content-type"])
        self.assertIn("attachment; filename=\"contextiq-research-report.txt\"", resp.headers["content-disposition"])
        self.assertIn("ContextIQ Research Report", resp.text)
