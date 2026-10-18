# tests/test_agentic_research.py
#
# Phase C11: bounded agentic research. Retriever, LLM, verifier and
# contradiction detector are mocked; scope uses the temp metadata DB.

import json
import unittest
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from agentic_research import (
    AgenticResearcher,
    CancelToken,
    ResearchLimits,
    heuristic_plan,
    is_simple,
    run_to_completion,
)
from metadata_store import MetadataStore


def _chunk(filename, idx, text, sim=0.8):
    return {"filename": filename, "chunk_id": f"{filename}-{idx}", "chunk_text": text,
            "similarity": sim, "page": idx + 1}


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class AgentTestBase(unittest.TestCase):
    def setUp(self):
        tag = uuid.uuid4().hex[:8]
        self.coll = MetadataStore.create_collection(f"Agent {tag}")
        self.doc_in = f"in_{tag}.txt"
        self.doc_out = f"out_{tag}.txt"
        MetadataStore.upsert_document(self.doc_in, "txt", collection_id=self.coll["id"])
        MetadataStore.upsert_document(self.doc_out, "txt")
        self.in_chunk = _chunk(self.doc_in, 0, "Revenue grew 25% in 2024 because of cloud demand.")
        self.in_chunk2 = _chunk(self.doc_in, 1, "Costs fell 5% after automation.")
        self.out_chunk = _chunk(self.doc_out, 0, "SECRET: other collection data.")

    def tearDown(self):
        MetadataStore.delete_document_meta(self.doc_in)
        MetadataStore.delete_document_meta(self.doc_out)
        MetadataStore.delete_collection(self.coll["id"])

    def _llm(self, plan=None, answer="## Summary\nRevenue grew 25% [S1]. Costs fell [S2] [S9].",
             plan_raises=None, stream_raises=None, reformulation="cloud revenue growth"):
        llm = MagicMock()

        def generate(system, prompt, **kw):
            if "plan document research" in system:
                if plan_raises:
                    raise plan_raises
                return json.dumps({"subquestions": plan or []})
            return json.dumps({"query": reformulation})

        llm.generate.side_effect = generate
        if stream_raises:
            llm.generate_stream.side_effect = stream_raises
        else:
            llm.generate_stream.side_effect = lambda *a, **k: iter([answer[:20], answer[20:]])
        return llm

    def _researcher(self, retriever, llm, limits=None, clock=None):
        verifier = MagicMock()
        verifier.verify_citations.return_value = [
            {"claim": "Revenue grew 25% in 2024.", "status": "SUPPORTED",
             "citation_ids": [self.in_chunk["chunk_id"]], "reason": "ok"}
        ]
        detector = MagicMock()
        detector.detect_contradictions.return_value = []
        return AgenticResearcher(retriever, llm=llm, limits=limits or ResearchLimits(),
                                 verifier=verifier, detector=detector, clock=clock or FakeClock())


class PlanningTests(unittest.TestCase):
    def test_simple_questions_are_not_split(self):
        self.assertTrue(is_simple("What was revenue in 2024?"))
        self.assertFalse(is_simple("How did revenue change and what drove costs over the period?"))
        self.assertEqual(heuristic_plan("Who founded Acme? Where is it based?", 4),
                         ["Who founded Acme?", "Where is it based?"])
        self.assertEqual(heuristic_plan("Compare revenue and costs", 4), ["Compare revenue and costs"])


class AgenticResearchTests(AgentTestBase):
    def test_simple_question_completes_with_valid_citations(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = [self.in_chunk, self.in_chunk2]
        llm = self._llm()
        events = list(self._researcher(retriever, llm).run("What was revenue in 2024?",
                                                           collection_id=self.coll["id"]))
        result = events[-1]["result"]
        types = [e["type"] for e in events]
        self.assertEqual(types[0], "progress")
        self.assertIn("plan", types)
        self.assertIn("token", types)
        self.assertEqual(result["plan_method"], "single")
        self.assertEqual(len(result["subquestions"]), 1)
        # [S9] does not exist and is stripped; [S1]/[S2] stay.
        self.assertNotIn("[S9]", result["answer"])
        self.assertIn("[S1]", result["answer"])
        self.assertTrue(any("non-existent" in w for w in result["warnings"]))
        self.assertEqual([s["label"] for s in result["sources"]], ["S1", "S2"])
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["evidence_assessment"]["claims"][0]["rating"], "MODERATE")
        llm.generate.assert_not_called()  # simple question: no planning call

    def test_complex_question_is_planned_within_limits(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = [self.in_chunk]
        llm = self._llm(plan=["How did revenue change?", "How did revenue change?",
                              "What happened to costs?", "What drove growth?", "Extra one?", "Too many?"])
        limits = ResearchLimits(max_subquestions=3)
        result = run_to_completion(self._researcher(retriever, llm, limits),
                                   "How did revenue and costs change over the year, and why?",
                                   collection_id=self.coll["id"])
        self.assertEqual(result["plan_method"], "llm")
        self.assertEqual(len(result["subquestions"]), 3)  # deduped and capped
        self.assertLessEqual(result["limits"]["retrievals_used"], limits.max_retrievals)

    def test_scope_enforced_on_every_retrieval(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = [self.in_chunk, self.out_chunk]  # leak attempt
        llm = self._llm(plan=["Revenue in 2024?", "Costs in 2024?"])
        result = run_to_completion(self._researcher(retriever, llm),
                                   "How did revenue and costs change during 2024?",
                                   collection_id=self.coll["id"])
        for call in retriever.retrieve.call_args_list:
            self.assertEqual(call.kwargs["filenames"], [self.doc_in])
        self.assertEqual({s["filename"] for s in result["sources"]}, {self.doc_in})
        prompt = llm.generate_stream.call_args.args[1]
        self.assertNotIn("SECRET", prompt)

    def test_gaps_trigger_bounded_followups_without_repeating_queries(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = []  # nothing ever found
        llm = self._llm(plan=["Revenue in 2024?", "Costs in 2024?", "Headcount in 2024?"],
                        reformulation="Revenue in 2024?")  # model suggests an already-run query
        limits = ResearchLimits(max_followups=2, max_retrievals=10)
        result = run_to_completion(self._researcher(retriever, llm, limits),
                                   "What happened to revenue and costs and headcount in 2024?",
                                   collection_id=self.coll["id"])
        queries = [c.args[0] for c in retriever.retrieve.call_args_list]
        normalized = [" ".join(sorted(q.lower().split())) for q in queries]
        self.assertEqual(len(normalized), len(set(normalized)))  # no identical search twice
        self.assertLessEqual(result["limits"]["followups_used"], 2)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(len(result["unresolved"]), 3)
        llm.generate_stream.assert_not_called()  # no evidence -> no synthesis

    def test_retrieval_limit_is_hard(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = []
        llm = self._llm(plan=["A question one?", "A question two?", "A question three?", "A question four?"])
        limits = ResearchLimits(max_retrievals=2, max_followups=5)
        result = run_to_completion(self._researcher(retriever, llm, limits),
                                   "Tell me about one and two and three and four in detail?",
                                   collection_id=self.coll["id"])
        self.assertEqual(retriever.retrieve.call_count, 2)
        self.assertEqual(result["limits"]["retrievals_used"], 2)

    def test_model_unavailable_gives_partial_result_with_evidence(self):
        import requests

        retriever = MagicMock()
        retriever.retrieve.return_value = [self.in_chunk]
        llm = self._llm(plan_raises=requests.ConnectionError("down"))
        result = run_to_completion(self._researcher(retriever, llm),
                                   "How did revenue and costs change over the year, and why?",
                                   collection_id=self.coll["id"])
        self.assertEqual(result["plan_method"], "heuristic")
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["answer"], "")
        self.assertTrue(result["sources"])
        llm.generate_stream.assert_not_called()  # no repeated calls after a failure

    def test_missing_citation_check_is_surfaced(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = [self.in_chunk, self.in_chunk2]
        researcher = self._researcher(retriever, self._llm())
        researcher.verifier.verify_citations.return_value = []  # e.g. model timed out
        result = run_to_completion(researcher, "What was revenue in 2024?", collection_id=self.coll["id"])
        self.assertIsNone(result["evidence_assessment"])
        self.assertTrue(any("citation check returned no results" in w for w in result["warnings"]))

    def test_synthesis_failure_is_partial(self):
        import requests

        retriever = MagicMock()
        retriever.retrieve.return_value = [self.in_chunk]
        llm = self._llm(stream_raises=requests.ReadTimeout("slow"))
        result = run_to_completion(self._researcher(retriever, llm), "What was revenue in 2024?",
                                   collection_id=self.coll["id"])
        self.assertEqual(result["status"], "PARTIAL")
        self.assertTrue(any("failed while writing" in w for w in result["warnings"]))

    def test_time_budget_stops_the_run(self):
        clock = FakeClock()
        retriever = MagicMock()

        def slow_retrieve(*a, **k):
            clock.t += 200  # each search "takes" 200s against a 300s budget
            return [self.in_chunk]

        retriever.retrieve.side_effect = slow_retrieve
        llm = self._llm(plan=["Revenue in 2024?", "Costs in 2024?", "Margins in 2024?"])
        result = run_to_completion(self._researcher(retriever, llm, ResearchLimits(time_budget_s=300), clock),
                                   "What happened to revenue and costs and margins in 2024?",
                                   collection_id=self.coll["id"])
        self.assertEqual(retriever.retrieve.call_count, 2)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertTrue(any("time budget" in w for w in result["warnings"]))

    def test_cancellation_mid_stream(self):
        retriever = MagicMock()
        retriever.retrieve.return_value = [self.in_chunk]
        llm = self._llm()
        cancel = CancelToken()
        events = []
        for e in self._researcher(retriever, llm).run("What was revenue in 2024?",
                                                      collection_id=self.coll["id"], cancel=cancel):
            events.append(e)
            if e["type"] == "token":
                cancel.cancel()
        result = events[-1]["result"]
        self.assertEqual(result["status"], "CANCELLED")
        self.assertEqual(sum(1 for e in events if e["type"] == "token"), 1)

    def test_scope_errors_raise_before_any_event(self):
        researcher = self._researcher(MagicMock(), self._llm())
        with self.assertRaises(PermissionError):
            next(researcher.run("q?", collection_id=self.coll["id"], filenames=[self.doc_out]))


class AgentApiTests(AgentTestBase):
    def test_stream_and_blocking_endpoints(self):
        from api.main import app

        retriever = MagicMock()
        retriever.retrieve.return_value = [self.in_chunk]
        rag = MagicMock()
        rag.retriever = retriever
        rag.enrich_sources.side_effect = lambda s: s

        def fake_researcher(ret, limits=None):
            return self._researcher(ret, self._llm(), limits)

        with patch("api.routers.agent_research.get_rag_service", return_value=rag), \
             patch("api.routers.agent_research.AgenticResearcher", side_effect=fake_researcher):
            client = TestClient(app)
            r = client.post("/research/agent/stream",
                            json={"question": "What was revenue in 2024?", "collection_id": self.coll["id"]})
            self.assertEqual(r.status_code, 200)
            frames = [json.loads(line[6:]) for line in r.text.splitlines() if line.startswith("data: ")]
            self.assertEqual(frames[-1]["type"], "done")
            self.assertEqual(frames[-2]["type"], "result")

            r = client.post("/research/agent", json={"question": "What was revenue in 2024?",
                                                     "collection_id": self.coll["id"]})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["status"], "COMPLETED")

            r = client.post("/research/agent/stream", json={"question": "q?", "collection_id": "missing"})
            self.assertEqual(r.status_code, 400)
            r = client.post("/research/agent", json={"question": "   "})
            self.assertEqual(r.status_code, 422)

    def test_report_includes_research_process(self):
        from report_service import ResearchReportService

        md = ResearchReportService().generate_markdown({
            "question": "q", "answer": "a", "research_status": "PARTIAL",
            "subquestions": [{"question": "Revenue?", "status": "ANSWERED", "source_labels": ["S1"]},
                             {"question": "Costs?", "status": "UNRESOLVED", "source_labels": [],
                              "note": "No relevant passages."}],
            "unresolved": ["Costs?"],
        })
        self.assertIn("## Research Process", md)
        self.assertIn("**UNRESOLVED**: Costs? (no sources)", md)
        self.assertIn("## Unresolved Questions", md)


if __name__ == "__main__":
    unittest.main()
