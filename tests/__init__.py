# tests/__init__.py
#
# Point every test run at a throwaway data folder and vector store.
#
# config.py reads CONTEXTIQ_DATA_DIR / CONTEXTIQ_CHROMA_DIR at import
# time and metadata_store.py opens <DATA_DIR>/metadata.db on import, so
# this must run before any project module is imported. Being the
# package __init__, it executes first under both `pytest` and
# `python -m unittest tests.test_x`. Without it, test runs wrote fixture
# collections and documents into the developer's real knowledge base.
#
# Set CONTEXTIQ_TEST_USE_REAL_DATA=1 to opt out (the live end-to-end
# suite in tests/test_api.py needs the real, populated store).

import os
import tempfile

if os.environ.get("CONTEXTIQ_TEST_USE_REAL_DATA") != "1":
    _root = tempfile.mkdtemp(prefix="contextiq-tests-")
    os.environ["CONTEXTIQ_DATA_DIR"] = os.path.join(_root, "data")
    os.environ["CONTEXTIQ_CHROMA_DIR"] = os.path.join(_root, "chroma_db")
    os.makedirs(os.environ["CONTEXTIQ_DATA_DIR"], exist_ok=True)
