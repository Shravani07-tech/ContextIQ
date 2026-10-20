# tests/test_kb_hygiene.py
#
# Guards against repository files leaking into the knowledge base: the
# data folder's README.md must never be picked up by "index everything",
# uploads must not overwrite it, and un-indexing a document must keep
# its file on disk. Runs in the temp data dir from tests/__init__.py.

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from config import DATA_DIR
from metadata_store import MetadataStore

ROOT = Path(__file__).resolve().parent.parent


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IndexAllExclusionTests(unittest.TestCase):
    def setUp(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.files = {
            "README.md": "# Knowledge-base documents\nThis folder is where ContextIQ reads documents.",
            "kb_hygiene_notes.md": "# Notes\nReal knowledge content.",
        }
        for name, text in self.files.items():
            with open(os.path.join(DATA_DIR, name), "w", encoding="utf-8") as f:
                f.write(text)

    def tearDown(self):
        for name in self.files:
            path = os.path.join(DATA_DIR, name)
            if os.path.exists(path):
                os.remove(path)

    def test_index_everything_skips_the_folder_readme(self):
        from api.services.document_service import DocumentService

        listed = DocumentService().list_data_files()
        self.assertIn("kb_hygiene_notes.md", listed)
        self.assertNotIn("README.md", listed)

    def test_cli_ingest_skips_the_folder_readme(self):
        from ingest import load_documents

        names = {d["filename"] for d in load_documents(DATA_DIR)}
        self.assertIn("kb_hygiene_notes.md", names)
        self.assertNotIn("README.md", names)

    def test_upload_cannot_overwrite_reserved_files(self):
        from api.services.document_service import DocumentService

        for name in ("README.md", "readme.MD"):
            with self.assertRaises(ValueError):
                DocumentService().save_upload(name, b"overwrite attempt")
        with open(os.path.join(DATA_DIR, "README.md"), encoding="utf-8") as f:
            self.assertIn("Knowledge-base documents", f.read())


class UnindexScriptTests(unittest.TestCase):
    NAME = "kb_hygiene_sample.txt"

    def setUp(self):
        from vector_store import get_collection

        self.path = os.path.join(DATA_DIR, self.NAME)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("Sample text that must stay on disk.")
        MetadataStore.upsert_document(self.NAME, "txt", chunk_count=2)
        MetadataStore.save_summary(self.NAME, "A summary.", ["point"])
        self.collection = get_collection()
        self.collection.add(
            ids=[f"{self.NAME}-0", f"{self.NAME}-1", "other_doc.txt-0"],
            embeddings=[[0.1] * 384, [0.2] * 384, [0.3] * 384],
            documents=["a", "b", "c"],
            metadatas=[{"filename": self.NAME}, {"filename": self.NAME}, {"filename": "other_doc.txt"}],
        )

    def tearDown(self):
        self.collection.delete(where={"filename": {"$in": [self.NAME, "other_doc.txt"]}})
        MetadataStore.delete_summary(self.NAME)
        MetadataStore.delete_document_meta(self.NAME)
        if os.path.exists(self.path):
            os.remove(self.path)

    def _run(self, *args):
        script = _load_script("unindex_documents")
        with patch.object(sys, "argv", ["unindex_documents.py", *args]):
            return script.main()

    def test_dry_run_changes_nothing(self):
        self.assertEqual(self._run(self.NAME), 0)
        self.assertEqual(len(self.collection.get(where={"filename": self.NAME})["ids"]), 2)
        self.assertIsNotNone(MetadataStore.get_document(self.NAME))

    def test_apply_removes_index_data_but_keeps_file_and_other_documents(self):
        self.assertEqual(self._run("--apply", self.NAME), 0)
        self.assertEqual(self.collection.get(where={"filename": self.NAME})["ids"], [])
        self.assertIsNone(MetadataStore.get_document(self.NAME))
        self.assertIsNone(MetadataStore.get_summary(self.NAME))
        self.assertTrue(os.path.isfile(self.path))  # file kept
        self.assertEqual(self.collection.get(where={"filename": "other_doc.txt"})["ids"], ["other_doc.txt-0"])


if __name__ == "__main__":
    unittest.main()
