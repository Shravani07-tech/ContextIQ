# tests/test_collection_hygiene.py
#
# Guards against the repeated "Collection A/B" and QA collections that
# accumulated in the real sidebar: tests must never use the real data
# directory, the API must refuse look-alike duplicate names, and the
# cleanup script must only ever touch empty fixture collections.

import os
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

import config
from metadata_store import MetadataStore

ROOT = Path(__file__).resolve().parent.parent


class TestDataIsolationTests(unittest.TestCase):
    def test_tests_never_use_the_real_data_directory(self):
        if os.environ.get("CONTEXTIQ_TEST_USE_REAL_DATA") == "1":
            self.skipTest("explicit opt-in to the real data directory")
        self.assertNotEqual(Path(config.DATA_DIR).resolve(), (ROOT / "data").resolve())
        self.assertNotEqual(Path(config.CHROMA_DB_DIR).resolve(), (ROOT / "chroma_db").resolve())


class DuplicateNameTests(unittest.TestCase):
    def setUp(self):
        from api.main import app

        self.client = TestClient(app)
        self.name = f"Research {uuid.uuid4().hex[:6]}"
        self.created: list[str] = []

    def tearDown(self):
        for cid in self.created:
            MetadataStore.delete_collection(cid)

    def _create(self, name):
        r = self.client.post("/collections", json={"name": name})
        if r.status_code == 201:
            self.created.append(r.json()["id"])
        return r

    def test_create_rejects_case_insensitive_duplicate(self):
        self.assertEqual(self._create(self.name).status_code, 201)
        r = self._create(f"  {self.name.upper()} ")
        self.assertEqual(r.status_code, 409)
        self.assertIn("already exists", r.json()["detail"])

    def test_rename_rules(self):
        first = self._create(self.name).json()
        second = self._create(f"{self.name} two").json()
        r = self.client.patch(f"/collections/{second['id']}", json={"name": self.name.lower()})
        self.assertEqual(r.status_code, 409)
        # Renaming a collection to its own name (or changing only the
        # description) is not a conflict.
        r = self.client.patch(f"/collections/{first['id']}", json={"name": self.name, "description": "x"})
        self.assertEqual(r.status_code, 200)
        r = self.client.patch(f"/collections/{first['id']}", json={"name": "   "})
        self.assertEqual(r.status_code, 422)


class CleanupScriptTests(unittest.TestCase):
    SCRIPT = str(ROOT / "scripts" / "cleanup_test_collections.py")

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, self.SCRIPT, *args],
            capture_output=True, text=True, env=os.environ.copy(), cwd=str(ROOT),
        )

    def setUp(self):
        self.empty_fixture = MetadataStore.create_collection("Collection A")
        self.used_fixture = MetadataStore.create_collection("Movement Target Collection")
        self.real = MetadataStore.create_collection(f"My Real Research {uuid.uuid4().hex[:6]}")
        self.doc = f"kept_{uuid.uuid4().hex[:6]}.txt"
        MetadataStore.upsert_document(self.doc, "txt", collection_id=self.used_fixture["id"])

    def tearDown(self):
        MetadataStore.delete_document_meta(self.doc)
        for c in (self.empty_fixture, self.used_fixture, self.real):
            MetadataStore.delete_collection(c["id"])

    def test_dry_run_lists_only_empty_fixture_collections_and_deletes_nothing(self):
        out = self._run()
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn(self.empty_fixture["id"], out.stdout)
        self.assertNotIn(self.used_fixture["id"], out.stdout)  # has a document
        self.assertNotIn(self.real["id"], out.stdout)  # not a fixture name
        self.assertIn("nothing deleted", out.stdout)
        self.assertIsNotNone(MetadataStore.get_collection(self.empty_fixture["id"]))

    def test_apply_refuses_non_candidates_and_deletes_only_listed_ids(self):
        refused = self._run("--apply", "--ids", self.empty_fixture["id"], self.real["id"])
        self.assertEqual(refused.returncode, 1)
        self.assertIsNotNone(MetadataStore.get_collection(self.empty_fixture["id"]))
        self.assertIsNotNone(MetadataStore.get_collection(self.real["id"]))

        done = self._run("--apply", "--ids", self.empty_fixture["id"])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIsNone(MetadataStore.get_collection(self.empty_fixture["id"]))
        self.assertIsNotNone(MetadataStore.get_collection(self.used_fixture["id"]))
        self.assertIsNotNone(MetadataStore.get_document(self.doc))


if __name__ == "__main__":
    unittest.main()
