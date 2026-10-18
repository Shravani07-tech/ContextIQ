# tests/test_graph.py
#
# Phase C10: evidence-linked knowledge graph. Uses the throwaway SQLite
# database from tests/__init__.py; the LLM and vector store are mocked.

import json
import unittest
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from graph_service import GraphService, entity_id_for, normalize_entity_name
from metadata_store import MetadataStore


def _chunk(filename, idx, text):
    return {"filename": filename, "chunk_id": f"{filename}-{idx}", "chunk_text": text,
            "page": idx + 1, "slide": None, "sheet": None, "section": None, "document_id": filename}


class NormalizationTests(unittest.TestCase):
    def test_conservative_normalization(self):
        self.assertEqual(normalize_entity_name("  The  Acme   Corp. "), "acme corp")
        self.assertEqual(normalize_entity_name("Jane Doe's"), "jane doe")
        self.assertEqual(normalize_entity_name("“Project Atlas”"), normalize_entity_name("project atlas"))
        # Suffixes are NOT stripped: these stay distinct entities.
        self.assertNotEqual(normalize_entity_name("Acme"), normalize_entity_name("Acme Corp"))
        self.assertEqual(entity_id_for("ORGANIZATION", "acme"), entity_id_for("ORGANIZATION", "acme"))
        self.assertNotEqual(entity_id_for("ORGANIZATION", "acme"), entity_id_for("PERSON", "acme"))


class GraphServiceTests(unittest.TestCase):
    def setUp(self):
        GraphService.clear()
        tag = uuid.uuid4().hex[:8]
        self.coll_a = MetadataStore.create_collection(f"Graph A {tag}")
        self.coll_b = MetadataStore.create_collection(f"Graph B {tag}")
        self.doc_a = f"acme_{tag}.txt"
        self.doc_b = f"globex_{tag}.txt"
        MetadataStore.upsert_document(self.doc_a, "txt", collection_id=self.coll_a["id"])
        MetadataStore.upsert_document(self.doc_b, "txt", collection_id=self.coll_b["id"])
        self.chunks = {
            self.doc_a: [
                _chunk(self.doc_a, 0, "Jane Doe founded Acme Corp in Berlin. Acme Corp builds Project Atlas."),
                _chunk(self.doc_a, 1, "Acme later partnered with the World Health Organization (WHO)."),
            ],
            self.doc_b: [_chunk(self.doc_b, 0, "Hank Scorpio runs Globex Corporation in Cypress Creek.")],
        }
        p = patch("vector_store.get_document_chunks",
                  side_effect=lambda name, limit=200: self.chunks.get(name, []))
        p.start()
        self.addCleanup(p.stop)
        prev = patch.object(GraphService, "_previews", staticmethod(
            lambda ids: {c["chunk_id"]: c["chunk_text"] for cs in self.chunks.values() for c in cs}))
        prev.start()
        self.addCleanup(prev.stop)

    def tearDown(self):
        GraphService.clear()
        for d in (self.doc_a, self.doc_b):
            MetadataStore.delete_document_meta(d)
        MetadataStore.delete_collection(self.coll_a["id"])
        MetadataStore.delete_collection(self.coll_b["id"])

    def _llm(self, payload_by_doc):
        llm = MagicMock()

        def gen(system, prompt, **kw):
            for marker, payload in payload_by_doc.items():
                if marker in prompt:
                    return json.dumps(payload)
            return json.dumps({"entities": [], "relations": []})

        llm.generate.side_effect = gen
        return llm

    ACME = {
        "entities": [
            {"name": "Jane Doe", "type": "PERSON", "evidence_ids": ["E1"]},
            {"name": "Acme Corp", "type": "ORGANIZATION", "evidence_ids": ["E1"]},
            {"name": "acme corp", "type": "ORGANIZATION", "evidence_ids": ["E1"]},  # same entity
            {"name": "Acme", "type": "ORGANIZATION", "evidence_ids": ["E2"]},
            {"name": "Berlin", "type": "PLACE", "evidence_ids": ["E1"]},
            {"name": "World Health Organization", "type": "ORGANIZATION", "evidence_ids": ["E2"]},
            {"name": "WHO", "type": "ORGANIZATION", "evidence_ids": ["E2"]},
            {"name": "Imaginary Ltd", "type": "ORGANIZATION", "evidence_ids": ["E1"]},  # not in text
        ],
        "relations": [
            {"source": "Jane Doe", "target": "Acme Corp", "relation": "founded",
             "evidence_id": "E1", "quote": "Jane Doe founded Acme Corp"},
            {"source": "Acme Corp", "target": "Berlin", "relation": "located in",
             "evidence_id": "E1", "quote": "a paraphrase that is not in the text"},
            {"source": "Jane Doe", "target": "Imaginary Ltd", "relation": "owns",
             "evidence_id": "E1", "quote": "Jane Doe owns Imaginary Ltd"},
            {"source": "Jane Doe", "target": "Berlin", "relation": "born in",
             "evidence_id": "E9", "quote": "Jane Doe"},
        ],
    }

    def test_extraction_validates_entities_and_evidence_linked_edges(self):
        svc = GraphService(llm=self._llm({"Jane Doe founded": self.ACME}))
        out = svc.build(filenames=[self.doc_a])
        self.assertEqual(out["processed"][0]["status"], "completed")
        self.assertEqual(out["processed"][0]["method"], "llm")

        graph = svc.get_graph(filenames=[self.doc_a])
        names = {n["name"] for n in graph["nodes"]}
        self.assertIn("Acme Corp", names)
        self.assertNotIn("Imaginary Ltd", names)  # name absent from passage
        self.assertEqual(sum(1 for n in graph["nodes"] if n["name"].lower() == "acme corp"), 1)

        edges = {(e["relation"], e["status"]) for e in graph["edges"]}
        self.assertIn(("founded", "SUPPORTED"), edges)
        self.assertIn(("located in", "UNCERTAIN"), edges)  # quote not found verbatim
        self.assertNotIn("owns", {e["relation"] for e in graph["edges"]})
        self.assertNotIn("born in", {e["relation"] for e in graph["edges"]})  # invalid evidence id

        dup_reasons = {(d["a_name"], d["b_name"], d["reason"]) for d in graph["possible_duplicates"]}
        flat = {frozenset((a, b)) for a, b, _ in dup_reasons}
        self.assertIn(frozenset(("Acme", "Acme Corp")), flat)
        self.assertIn(frozenset(("WHO", "World Health Organization")), flat)

    def test_entity_detail_links_to_sources_and_persists(self):
        svc = GraphService(llm=self._llm({"Jane Doe founded": self.ACME}))
        svc.build(filenames=[self.doc_a])
        node = next(n for n in GraphService().get_graph(filenames=[self.doc_a])["nodes"] if n["name"] == "Jane Doe")

        # A fresh service instance reads the persisted rows.
        detail = GraphService(llm=MagicMock()).get_entity(node["id"], filenames=[self.doc_a])
        self.assertEqual(detail["entity"]["type"], "PERSON")
        self.assertEqual(detail["mentions"][0]["source"]["chunk_id"], f"{self.doc_a}-0")
        self.assertEqual(detail["mentions"][0]["source"]["page"], 1)
        founded = next(r for r in detail["relations"] if r["relation"] == "founded")
        self.assertEqual(founded["status"], "SUPPORTED")
        self.assertEqual(founded["evidence"], "Jane Doe founded Acme Corp")
        self.assertEqual(founded["other"]["name"], "Acme Corp")
        self.assertIn("Jane Doe founded", founded["source"]["preview"])

    def test_collection_isolation_for_nodes_edges_and_entities(self):
        globex = {"entities": [{"name": "Hank Scorpio", "type": "PERSON", "evidence_ids": ["E1"]},
                               {"name": "Globex Corporation", "type": "ORGANIZATION", "evidence_ids": ["E1"]}],
                  "relations": [{"source": "Hank Scorpio", "target": "Globex Corporation", "relation": "runs",
                                 "evidence_id": "E1", "quote": "Hank Scorpio runs Globex Corporation"}]}
        svc = GraphService(llm=self._llm({"Jane Doe founded": self.ACME, "Hank Scorpio": globex}))
        # Whole knowledge base, in bounded batches until nothing remains.
        for _ in range(20):
            if svc.build()["remaining"] == 0:
                break

        graph_a = svc.get_graph(collection_id=self.coll_a["id"])
        names_a = {n["name"] for n in graph_a["nodes"]}
        self.assertIn("Jane Doe", names_a)
        self.assertNotIn("Hank Scorpio", names_a)
        self.assertNotIn("runs", {e["relation"] for e in graph_a["edges"]})

        hank = next(n for n in svc.get_graph(collection_id=self.coll_b["id"])["nodes"] if n["name"] == "Hank Scorpio")
        self.assertIsNone(svc.get_entity(hank["id"], collection_id=self.coll_a["id"]))
        with self.assertRaises(PermissionError):
            svc.get_graph(collection_id=self.coll_a["id"], filenames=[self.doc_b])

    def test_empty_graph_and_failed_extraction_fallback(self):
        svc = GraphService(llm=MagicMock())
        empty = svc.get_graph(filenames=[self.doc_a])
        self.assertEqual(empty["nodes"], [])
        self.assertEqual(empty["documents_extracted"], 0)

        import requests

        down = MagicMock()
        down.generate.side_effect = requests.ConnectionError("ollama down")
        out = GraphService(llm=down).build(filenames=[self.doc_a])
        self.assertEqual(out["processed"][0]["method"], "pattern")
        graph = svc.get_graph(filenames=[self.doc_a])
        self.assertTrue(graph["nodes"])
        # Co-mentions are never presented as confirmed relationships.
        self.assertTrue(all(e["status"] == "UNCERTAIN" for e in graph["edges"]))
        self.assertTrue(all(e["relation"] == "mentioned with" for e in graph["edges"]))

    def test_rebuild_is_skipped_unless_forced_and_delete_cleans_up(self):
        llm = self._llm({"Jane Doe founded": self.ACME})
        svc = GraphService(llm=llm)
        svc.build(filenames=[self.doc_a])
        calls = llm.generate.call_count
        self.assertEqual(svc.build(filenames=[self.doc_a])["processed"], [])
        self.assertEqual(llm.generate.call_count, calls)
        svc.build(filenames=[self.doc_a], force=True)
        self.assertGreater(llm.generate.call_count, calls)

        GraphService.delete_document(self.doc_a)
        graph = svc.get_graph(filenames=[self.doc_a])
        self.assertEqual(graph["nodes"], [])
        self.assertEqual(graph["extractions"], [])

    def test_large_graph_is_truncated(self):
        svc = GraphService(llm=self._llm({"Jane Doe founded": self.ACME}))
        svc.build(filenames=[self.doc_a])
        graph = svc.get_graph(filenames=[self.doc_a], limit=2)
        self.assertEqual(len(graph["nodes"]), 2)
        self.assertTrue(graph["truncated"])
        ids = {n["id"] for n in graph["nodes"]}
        self.assertTrue(all(e["source"] in ids and e["target"] in ids for e in graph["edges"]))


class GraphApiTests(unittest.TestCase):
    def setUp(self):
        from api.main import app

        self.client = TestClient(app)

    def test_scope_errors_and_unknown_entity(self):
        self.assertEqual(self.client.get("/graph", params={"collection_id": "missing"}).status_code, 400)
        self.assertEqual(self.client.get("/graph/entities/ent_doesnotexist").status_code, 404)
        r = self.client.post("/graph/build", json={"filenames": ["nope.pdf"]})
        self.assertEqual(r.status_code, 400)

    def test_document_delete_removes_graph_facts(self):
        from api.services.document_service import DocumentService

        with patch("api.services.document_service.delete_document", return_value=0), \
             patch("graph_service.GraphService.delete_document") as mock_del:
            DocumentService().delete_document("whatever.txt")
        mock_del.assert_called_once_with("whatever.txt")


if __name__ == "__main__":
    unittest.main()
