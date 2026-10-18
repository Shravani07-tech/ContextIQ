# tests/test_timeline.py
#
# Phase C7: timeline extraction. The LLM and the vector store are mocked;
# metadata uses the throwaway SQLite database set up in tests/__init__.py.

import json
import unittest
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from date_normalizer import normalize_date, sort_key
from metadata_store import MetadataStore
from timeline_service import TimelineService


def _chunk(filename, idx, text, page=None):
    return {
        "filename": filename,
        "chunk_id": f"{filename}-{idx}",
        "chunk_text": text,
        "page": page,
        "section": None,
        "document_id": filename,
    }


class DateNormalizerTests(unittest.TestCase):
    def test_explicit_dates(self):
        self.assertEqual(normalize_date("March 3, 2024")["start"], "2024-03-03")
        self.assertEqual(normalize_date("3 March 2024")["precision"], "day")
        q = normalize_date("Q3 2023")
        self.assertEqual((q["start"], q["end"], q["precision"]), ("2023-07", "2023-09", "quarter"))
        r = normalize_date("between May 2020 and June 2021")
        self.assertEqual((r["start"], r["end"], r["precision"]), ("2020-05", "2021-06", "range"))
        iso_range = normalize_date("from 2024-03-01 to 2024-05-01")
        self.assertEqual((iso_range["start"], iso_range["end"]), ("2024-03-01", "2024-05-01"))

    def test_approximate_and_ambiguous_dates(self):
        self.assertEqual(normalize_date("mid-2019")["certainty"], "APPROXIMATE")
        self.assertEqual(normalize_date("circa 1850")["start"], "1850")
        decade = normalize_date("the 1990s")
        self.assertEqual((decade["start"], decade["end"]), ("1990", "1999"))
        amb = normalize_date("03/04/2024")
        self.assertEqual((amb["start"], amb["certainty"]), ("2024", "AMBIGUOUS"))
        self.assertEqual(normalize_date("13/04/2024")["start"], "2024-04-13")
        by = normalize_date("by 2025")
        self.assertEqual((by["qualifier"], by["certainty"]), ("by", "APPROXIMATE"))

    def test_relative_and_missing_dates_are_not_normalized(self):
        rel = normalize_date("last year")
        self.assertIsNone(rel["start"])
        self.assertEqual(rel["certainty"], "RELATIVE")
        missing = normalize_date("")
        self.assertIsNone(missing["start"])
        self.assertEqual(missing["certainty"], "UNKNOWN")
        self.assertIsNone(sort_key(missing))

    def test_partial_dates_sort_before_more_specific_ones(self):
        keys = [sort_key(normalize_date(t)) for t in ["2024-03-07", "2024", "March 2024"]]
        self.assertEqual(sorted(keys), [sort_key(normalize_date("2024")),
                                        sort_key(normalize_date("March 2024")),
                                        sort_key(normalize_date("2024-03-07"))])


class TimelineServiceTests(unittest.TestCase):
    def setUp(self):
        tag = uuid.uuid4().hex[:8]
        self.coll_a = MetadataStore.create_collection(f"Timeline A {tag}")
        self.coll_b = MetadataStore.create_collection(f"Timeline B {tag}")
        self.doc_a = f"history_a_{tag}.txt"
        self.doc_b = f"history_b_{tag}.txt"
        MetadataStore.upsert_document(self.doc_a, "txt", collection_id=self.coll_a["id"])
        MetadataStore.upsert_document(self.doc_b, "txt", collection_id=self.coll_b["id"])
        self.chunks = {
            self.doc_a: [
                _chunk(self.doc_a, 0, "Acme Corp was founded in March 2019 by Jane Doe.", page=1),
                _chunk(self.doc_a, 1, "Plain text with no dates at all."),
                _chunk(self.doc_a, 2, "The second plant opened in Q2 2021. Last year output doubled.", page=4),
                _chunk(self.doc_a, 3, "This report was published on 2024-01-15."),
            ],
            self.doc_b: [_chunk(self.doc_b, 0, "Secret merger agreed on June 1, 2020.")],
        }
        patcher = patch(
            "vector_store.get_document_chunks",
            side_effect=lambda name, limit=200: self.chunks.get(name, []),
        )
        self.mock_chunks = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        MetadataStore.delete_document_meta(self.doc_a)
        MetadataStore.delete_document_meta(self.doc_b)
        MetadataStore.delete_collection(self.coll_a["id"])
        MetadataStore.delete_collection(self.coll_b["id"])

    def _service(self, payload=None, raises=None):
        llm = MagicMock()
        if raises:
            llm.generate.side_effect = raises
        else:
            llm.generate.return_value = payload if isinstance(payload, str) else json.dumps(payload)
        return TimelineService(retriever=MagicMock(), llm=llm), llm

    def test_events_are_validated_ordered_and_linked_to_sources(self):
        # Evidence ids follow document order of the selected (dated) chunks:
        # E1 = chunk 0, E2 = chunk 2, E3 = chunk 3.
        svc, llm = self._service({
            "events": [
                {"evidence_id": "E2", "date_text": "Q2 2021", "date_type": "EVENT",
                 "description": "The second plant opened.", "actors": []},
                {"evidence_id": "E1", "date_text": "March 2019", "date_type": "EVENT",
                 "description": "Acme Corp was founded.", "actors": ["Jane Doe", "Invented Person"]},
                {"evidence_id": "E3", "date_text": "2024-01-15", "date_type": "PUBLICATION",
                 "description": "The report was published.", "actors": []},
                {"evidence_id": "E2", "date_text": "last year", "date_type": "EVENT",
                 "description": "Output doubled.", "actors": []},
                {"evidence_id": "E9", "date_text": "2030", "date_type": "EVENT",
                 "description": "Fabricated event citing a missing passage.", "actors": []},
                {"evidence_id": "E1", "date_text": "July 4, 1776", "date_type": "EVENT",
                 "description": "Date that is not in the passage.", "actors": []},
            ]
        })
        result = svc.build_timeline(collection_id=self.coll_a["id"])

        self.assertEqual(result["extraction_method"], "llm")
        self.assertEqual(result["events_discarded"], 1)
        descriptions = [e["description"] for e in result["events"]]
        self.assertEqual(descriptions, [
            "Acme Corp was founded.", "The second plant opened.", "The report was published.",
        ])
        founded = result["events"][0]
        self.assertEqual(founded["date"]["start"], "2019-03")
        self.assertTrue(founded["date"]["in_source"])
        self.assertEqual(founded["actors"], ["Jane Doe"])  # invented actor removed
        self.assertEqual(founded["source"]["chunk_id"], f"{self.doc_a}-0")
        self.assertEqual(founded["source"]["page"], 1)
        self.assertEqual(result["events"][1]["source"]["page"], 4)
        self.assertEqual(result["events"][2]["date_type"], "PUBLICATION")

        undated = {e["description"]: e for e in result["undated_events"]}
        self.assertEqual(undated["Output doubled."]["date"]["certainty"], "RELATIVE")
        not_in_source = undated["Date that is not in the passage."]["date"]
        self.assertFalse(not_in_source["in_source"])
        self.assertIsNone(not_in_source["start"])

        # Ingestion date reported separately, never as an event.
        self.assertEqual(result["document_dates"][0]["filename"], self.doc_a)
        self.assertIsNotNone(result["document_dates"][0]["indexed_at"])

    def test_collection_scope_limits_documents_read(self):
        svc, llm = self._service({"events": []})
        svc.build_timeline(collection_id=self.coll_a["id"])
        read = {call.args[0] for call in self.mock_chunks.call_args_list}
        self.assertEqual(read, {self.doc_a})
        prompt = llm.generate.call_args.args[1]
        self.assertNotIn("Secret merger", prompt)

    def test_document_outside_collection_is_rejected(self):
        svc, _ = self._service({"events": []})
        with self.assertRaises(PermissionError):
            svc.build_timeline(collection_id=self.coll_a["id"], filenames=[self.doc_b])
        with self.assertRaises(ValueError):
            svc.build_timeline(filenames=["does-not-exist.pdf"])

    def test_malformed_model_output_falls_back_to_patterns(self):
        svc, _ = self._service("this is not json at all")
        result = svc.build_timeline(filenames=[self.doc_a])
        self.assertEqual(result["extraction_method"], "pattern")
        self.assertTrue(result["warnings"])
        starts = [e["date"]["start"] for e in result["events"]]
        self.assertIn("2019-03", starts)
        self.assertIn("2021-04", starts)
        published = [e for e in result["events"] if e["date"]["start"] == "2024-01-15"]
        self.assertEqual(published[0]["date_type"], "PUBLICATION")
        for e in result["events"]:
            self.assertTrue(e["date"]["in_source"])

    def test_model_unavailable_falls_back(self):
        import requests

        svc, _ = self._service(raises=requests.ConnectionError("down"))
        result = svc.build_timeline(filenames=[self.doc_a])
        self.assertEqual(result["extraction_method"], "pattern")
        self.assertGreater(len(result["events"]), 0)

    def test_focus_mode_filters_out_of_scope_retrieval_results(self):
        svc, _ = self._service({"events": [
            {"evidence_id": "E1", "date_text": "March 2019", "description": "Founded.", "actors": []},
        ]})
        svc._retriever.retrieve.return_value = [
            dict(self.chunks[self.doc_a][0], similarity=0.9),
            dict(self.chunks[self.doc_b][0], similarity=0.8),  # leak attempt
        ]
        result = svc.build_timeline(collection_id=self.coll_a["id"], focus="founding")
        kwargs = svc._retriever.retrieve.call_args.kwargs
        self.assertEqual(kwargs["filenames"], [self.doc_a])
        self.assertEqual(result["chunks_analyzed"], 1)
        self.assertEqual(result["events"][0]["source"]["filename"], self.doc_a)

    def test_empty_scope_returns_empty_timeline(self):
        tag = uuid.uuid4().hex[:6]
        empty = MetadataStore.create_collection(f"Empty {tag}")
        try:
            svc, llm = self._service({"events": []})
            result = svc.build_timeline(collection_id=empty["id"])
            self.assertEqual(result["events"], [])
            self.assertEqual(result["extraction_method"], "none")
            llm.generate.assert_not_called()
        finally:
            MetadataStore.delete_collection(empty["id"])


class TimelineApiTests(unittest.TestCase):
    def setUp(self):
        from api.main import app

        patcher = patch("api.routers.timeline.get_rag_service")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(app)

    def test_unknown_collection_is_400(self):
        r = self.client.post("/timeline", json={"collection_id": "nope"})
        self.assertEqual(r.status_code, 400)

    def test_too_many_filenames_is_422(self):
        r = self.client.post("/timeline", json={"filenames": [f"f{i}.txt" for i in range(30)]})
        self.assertEqual(r.status_code, 422)

    @patch("timeline_service.TimelineService.build_timeline")
    def test_permission_error_is_403(self, mock_build):
        mock_build.side_effect = PermissionError("outside")
        r = self.client.post("/timeline", json={"filenames": ["a.txt"]})
        self.assertEqual(r.status_code, 403)


class TimelineReportTests(unittest.TestCase):
    def test_timeline_section_in_all_export_formats(self):
        from report_service import ResearchReportService

        payload = {
            "question": "Timeline",
            "answer": "Summary.",
            "sources": [],
            "timeline": [{
                "date": {"text": "Q3 2023", "certainty": "EXACT"},
                "date_type": "EVENT",
                "description": "Plant opened <script>.",
                "source": {"filename": "a.pdf", "page": 2},
            }],
        }
        svc = ResearchReportService()
        md = svc.generate_markdown(payload)
        self.assertIn("## Timeline", md)
        self.assertIn("**Q3 2023** (exact): Plant opened <script>. [a.pdf, p. 2]", md)
        self.assertIn("Q3 2023", svc.generate_txt(payload))
        self.assertTrue(svc.generate_pdf(payload).startswith(b"%PDF"))

    def test_export_api_accepts_timeline_and_hides_internal_errors(self):
        from api.main import app

        client = TestClient(app)
        body = {"format": "markdown", "question": "Q", "answer": "A", "timeline": [{
            "id": "evt-1",
            "date": {"text": "2021", "start": "2021", "end": "2021", "precision": "year",
                     "certainty": "EXACT", "in_source": True},
            "date_type": "EVENT", "description": "Thing happened.", "actors": [],
            "source": {"filename": "a.pdf", "chunk_id": "a.pdf-0"},
        }]}
        r = client.post("/research/export", json=body)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Thing happened.", r.text)

        with patch("report_service.ResearchReportService.generate_markdown",
                   side_effect=RuntimeError("C:/secret/path")):
            r = client.post("/research/export", json=body)
        self.assertEqual(r.status_code, 500)
        self.assertNotIn("secret", r.text)


if __name__ == "__main__":
    unittest.main()
