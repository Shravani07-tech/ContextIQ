# tests/test_evidence.py
#
# Phase C8: evidence and confidence assessment. The rating layer is
# deterministic, so most tests need no mocks at all; chat integration
# and the claim-check endpoint mock the LLM-backed services.

import unittest
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from evidence_service import DISCLAIMER, EvidenceService, check_claim, source_groups
from metadata_store import MetadataStore

CLAIM = "Revenue grew 25% in 2024 driven by cloud services."


def _chunk(filename, idx, text, similarity=0.8):
    return {"filename": filename, "chunk_id": f"{filename}-{idx}", "chunk_text": text,
            "similarity": similarity, "page": idx + 1}


SUPPORT_A = _chunk("annual_report.pdf", 0, "In 2024 revenue grew 25%, driven by cloud services demand.")
SUPPORT_B = _chunk("analyst_note.pdf", 3, "Analysts confirm cloud services drove 25% revenue growth during 2024.")
UNRELATED = _chunk("handbook.pdf", 1, "Employees receive twenty vacation days per year.")


class RatingRuleTests(unittest.TestCase):
    def setUp(self):
        self.svc = EvidenceService()

    def test_direct_support_from_two_independent_sources_is_strong(self):
        v = {"status": "SUPPORTED", "citation_ids": [SUPPORT_A["chunk_id"]]}
        r = self.svc.assess_claim(CLAIM, [SUPPORT_A, SUPPORT_B, UNRELATED], v, [])
        self.assertEqual(r["rating"], "STRONG")
        self.assertEqual(r["basis"], "model-assisted")
        self.assertEqual(r["factors"]["independent_sources"], 2)
        self.assertEqual(r["factors"]["directness"], "DIRECT")
        files = {p["filename"] for p in r["passages"]}
        self.assertEqual(files, {"annual_report.pdf", "analyst_note.pdf"})
        self.assertTrue(any(p["cited_by_check"] for p in r["passages"]))
        self.assertTrue(r["explanation"])

    def test_same_document_twice_counts_as_one_source(self):
        second = _chunk("annual_report.pdf", 5, "Cloud services pushed 2024 revenue up 25%.")
        v = {"status": "SUPPORTED", "citation_ids": []}
        r = self.svc.assess_claim(CLAIM, [SUPPORT_A, second], v, [])
        self.assertEqual(r["factors"]["independent_sources"], 1)
        self.assertEqual(r["rating"], "MODERATE")

    def test_near_duplicate_copies_are_not_independent_corroboration(self):
        copy = dict(SUPPORT_A, filename="annual_report_copy.pdf", chunk_id="annual_report_copy.pdf-0")
        groups = source_groups([SUPPORT_A, copy])
        self.assertEqual(groups[SUPPORT_A["chunk_id"]], groups[copy["chunk_id"]])
        r = self.svc.assess_claim(CLAIM, [SUPPORT_A, copy], {"status": "SUPPORTED", "citation_ids": []}, [])
        self.assertEqual(r["factors"]["independent_sources"], 1)
        self.assertEqual(r["factors"]["duplicates_collapsed"], 1)
        self.assertEqual(r["rating"], "MODERATE")
        self.assertTrue(any("near-identical" in e for e in r["explanation"]))

    def test_contradiction_overrides_support(self):
        contradiction = {"topic": "2024 revenue growth", "status": "CONTRADICTION", "severity": "HIGH",
                         "claim_a": "Revenue grew 25% in 2024.", "claim_b": "Revenue grew 12% in 2024.",
                         "source_a": "annual_report.pdf", "source_b": "analyst_note.pdf"}
        r = self.svc.assess_claim(CLAIM, [SUPPORT_A, SUPPORT_B],
                                  {"status": "SUPPORTED", "citation_ids": []}, [contradiction])
        self.assertEqual(r["rating"], "CONTESTED")
        self.assertEqual(r["factors"]["contradiction"], "CONFLICT")
        self.assertEqual(r["contradictions"][0]["severity"], "HIGH")

    def test_unrelated_contradiction_is_ignored(self):
        other = {"topic": "Vacation policy", "status": "CONTRADICTION", "severity": "HIGH",
                 "claim_a": "Employees get 20 days off.", "claim_b": "Employees get 15 days off."}
        r = self.svc.assess_claim(CLAIM, [SUPPORT_A, SUPPORT_B],
                                  {"status": "SUPPORTED", "citation_ids": []}, [other])
        self.assertEqual(r["rating"], "STRONG")

    def test_unsupported_is_never_upgraded_by_passage_volume(self):
        r = self.svc.assess_claim(CLAIM, [SUPPORT_A, SUPPORT_B],
                                  {"status": "UNSUPPORTED", "citation_ids": []}, [])
        self.assertEqual(r["rating"], "UNSUPPORTED")

    def test_insufficient_evidence(self):
        r = self.svc.assess_claim(CLAIM, [UNRELATED], {"status": "UNVERIFIABLE", "citation_ids": []}, [])
        self.assertEqual(r["rating"], "INSUFFICIENT")
        r2 = self.svc.assess_claim(CLAIM, [UNRELATED], None, [])
        self.assertEqual(r2["rating"], "INSUFFICIENT")
        self.assertEqual(r2["factors"]["independent_sources"], 0)

    def test_heuristic_only_without_model_check_is_capped_at_limited(self):
        r = self.svc.assess_claim(CLAIM, [SUPPORT_A, SUPPORT_B], None, [])
        self.assertEqual(r["rating"], "LIMITED")
        self.assertEqual(r["basis"], "heuristic")
        self.assertEqual(r["factors"]["directness"], "NOT_ASSESSED")

    def test_supported_verdict_without_locatable_passage_is_limited(self):
        r = self.svc.assess_claim(CLAIM, [UNRELATED], {"status": "SUPPORTED", "citation_ids": ["missing-9"]}, [])
        self.assertEqual(r["rating"], "LIMITED")

    def test_assess_answer_summary_and_disclaimer(self):
        verifications = [
            {"claim": CLAIM, "status": "SUPPORTED", "citation_ids": [SUPPORT_A["chunk_id"]]},
            {"claim": "Employees receive forty vacation days.", "status": "UNSUPPORTED", "citation_ids": []},
        ]
        out = self.svc.assess_answer(verifications, [SUPPORT_A, SUPPORT_B, UNRELATED], [])
        self.assertEqual(out["counts"]["STRONG"], 1)
        self.assertEqual(out["counts"]["UNSUPPORTED"], 1)
        self.assertEqual(out["disclaimer"], DISCLAIMER)
        self.assertIn("not calibrated probabilities", out["disclaimer"])
        self.assertIsNone(self.svc.assess_answer([], [SUPPORT_A], []))

    def test_coverage_by_document_flags_missing_evidence(self):
        cov = self.svc.coverage_by_document(["annual_report.pdf", "empty.pdf"], [SUPPORT_A])
        self.assertEqual(cov[0]["passages"], 1)
        self.assertEqual(cov[1]["passages"], 0)
        self.assertIn("No passages", cov[1]["note"])


class ChatIntegrationTests(unittest.TestCase):
    def _retriever(self):
        r = MagicMock()
        r.retrieve.return_value = [SUPPORT_A, SUPPORT_B]
        return r

    @patch("rag.ContradictionDetectionService")
    @patch("rag.CitationVerificationService")
    @patch("rag.SuggestedQuestionService")
    def test_answer_includes_evidence_assessment(self, mock_sq, mock_cv, mock_cd):
        from rag import answer_question

        mock_sq.return_value.generate_suggestions.return_value = []
        mock_cv.return_value.verify_citations.return_value = [
            {"claim": CLAIM, "status": "SUPPORTED", "citation_ids": [SUPPORT_A["chunk_id"]], "reason": "ok"}
        ]
        mock_cd.return_value.detect_contradictions.return_value = []
        llm = MagicMock()
        llm.generate.return_value = CLAIM

        result = answer_question("How did revenue change?", retriever=self._retriever(), llm=llm)
        self.assertEqual(result["evidence_assessment"]["claims"][0]["rating"], "STRONG")

    @patch("rag.ContradictionDetectionService")
    @patch("rag.CitationVerificationService")
    @patch("rag.SuggestedQuestionService")
    def test_stream_emits_evidence_event_and_skips_without_verification(self, mock_sq, mock_cv, mock_cd):
        from rag import answer_question_stream

        mock_sq.return_value.generate_suggestions.return_value = []
        mock_cd.return_value.detect_contradictions.return_value = []
        llm = MagicMock()
        llm.generate_stream.return_value = iter([CLAIM])

        mock_cv.return_value.verify_citations.return_value = [
            {"claim": CLAIM, "status": "PARTIALLY_SUPPORTED", "citation_ids": [], "reason": "part"}
        ]
        events = list(answer_question_stream("q", retriever=self._retriever(), llm=llm))
        ev = [e for e in events if e["type"] == "evidence_assessment"]
        self.assertEqual(ev[0]["assessment"]["claims"][0]["rating"], "LIMITED")
        sources = next(e for e in events if e["type"] == "sources")["sources"]
        self.assertIn("slide", sources[0])

        llm.generate_stream.return_value = iter([CLAIM])
        mock_cv.return_value.verify_citations.return_value = []
        events = list(answer_question_stream("q", retriever=self._retriever(), llm=llm))
        self.assertFalse([e for e in events if e["type"] == "evidence_assessment"])


class ClaimCheckTests(unittest.TestCase):
    def setUp(self):
        tag = uuid.uuid4().hex[:8]
        self.coll = MetadataStore.create_collection(f"Evidence {tag}")
        self.in_doc = SUPPORT_A["filename"]
        self.out_doc = SUPPORT_B["filename"]
        MetadataStore.upsert_document(self.in_doc, "pdf", collection_id=self.coll["id"])
        MetadataStore.upsert_document(self.out_doc, "pdf")

    def tearDown(self):
        MetadataStore.delete_document_meta(self.in_doc)
        MetadataStore.delete_document_meta(self.out_doc)
        MetadataStore.delete_collection(self.coll["id"])

    def test_out_of_scope_passages_never_reach_the_assessment(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = [SUPPORT_A, SUPPORT_B]  # B is outside the collection
        verifier = MagicMock()
        verifier.verify_citations.return_value = [
            {"claim": CLAIM, "status": "SUPPORTED", "citation_ids": [SUPPORT_A["chunk_id"]], "reason": "ok"}
        ]
        detector = MagicMock()
        detector.detect_contradictions.return_value = []

        out = check_claim(CLAIM, retriever, collection_id=self.coll["id"],
                          verifier=verifier, detector=detector)
        self.assertEqual(retriever.retrieve.call_args.kwargs["filenames"], [self.in_doc])
        passed_chunks = verifier.verify_citations.call_args.args[1]
        self.assertEqual({c["filename"] for c in passed_chunks}, {self.in_doc})
        self.assertEqual(out["assessment"]["rating"], "MODERATE")
        self.assertTrue(out["model_checked"])

    def test_document_outside_collection_rejected(self):
        with self.assertRaises(PermissionError):
            check_claim(CLAIM, MagicMock(), collection_id=self.coll["id"], filenames=[self.out_doc])

    def test_model_unavailable_degrades_to_heuristic(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = [SUPPORT_A]
        verifier = MagicMock()
        verifier.verify_citations.return_value = []  # service swallows LLM errors
        detector = MagicMock()
        detector.detect_contradictions.return_value = []
        out = check_claim(CLAIM, retriever, filenames=[self.in_doc], verifier=verifier, detector=detector)
        self.assertFalse(out["model_checked"])
        self.assertEqual(out["assessment"]["basis"], "heuristic")
        self.assertTrue(out["warnings"])

    def test_weakest_subclaim_verdict_governs(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = [SUPPORT_A]
        verifier = MagicMock()
        verifier.verify_citations.return_value = [
            {"claim": "Revenue grew 25%.", "status": "SUPPORTED", "citation_ids": [], "reason": ""},
            {"claim": "Growth came from hardware.", "status": "UNSUPPORTED", "citation_ids": [], "reason": ""},
        ]
        out = check_claim(CLAIM, retriever, filenames=[self.in_doc], verifier=verifier,
                          check_contradictions=False)
        self.assertEqual(out["assessment"]["rating"], "UNSUPPORTED")


class EvidenceApiTests(unittest.TestCase):
    def setUp(self):
        from api.main import app

        patcher = patch("api.routers.evidence.get_rag_service")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(app)

    def test_validation_and_scope_errors(self):
        self.assertEqual(self.client.post("/evidence/assess", json={"claim": "  "}).status_code, 422)
        r = self.client.post("/evidence/assess", json={"claim": "x", "collection_id": "missing"})
        self.assertEqual(r.status_code, 400)

    def test_report_includes_evidence_section(self):
        from report_service import ResearchReportService

        assessment = EvidenceService().assess_answer(
            [{"claim": CLAIM, "status": "SUPPORTED", "citation_ids": []}], [SUPPORT_A, SUPPORT_B], []
        )
        md = ResearchReportService().generate_markdown(
            {"question": "q", "answer": "a", "evidence_assessment": assessment}
        )
        self.assertIn("## Evidence Assessment", md)
        self.assertIn("**STRONG** (model-assisted)", md)
        self.assertIn("not calibrated probabilities", md)


if __name__ == "__main__":
    unittest.main()
