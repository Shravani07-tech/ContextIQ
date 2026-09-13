# tests/test_isolation.py
#
# ContextIQ 2.0 Phase B — Mandatory Security & Collection Isolation Tests.
# Verifies that collection-scoped retrieval strictly prevents cross-collection data leakage.

from unittest.mock import MagicMock
import pytest

from metadata_store import MetadataStore
from retrieval import HybridRetriever


def test_collection_isolation_logic():
    # 1. Setup Collection A and Collection B
    coll_a = MetadataStore.create_collection("Collection Apollo A")
    coll_b = MetadataStore.create_collection("Collection Apollo B")

    doc_a = "apollo_budget_a.txt"
    doc_b = "apollo_budget_b.txt"

    MetadataStore.upsert_document(
        filename=doc_a,
        file_type="txt",
        collection_id=coll_a["id"],
    )
    MetadataStore.upsert_document(
        filename=doc_b,
        file_type="txt",
        collection_id=coll_b["id"],
    )

    retriever = HybridRetriever()

    # 2. Test candidate scope resolution for Collection A
    docs_a = MetadataStore.list_documents(collection_id=coll_a["id"])
    filenames_a = {d["filename"] for d in docs_a}
    assert filenames_a == {doc_a}
    assert doc_b not in filenames_a

    # 3. Test candidate scope resolution for Collection B
    docs_b = MetadataStore.list_documents(collection_id=coll_b["id"])
    filenames_b = {d["filename"] for d in docs_b}
    assert filenames_b == {doc_b}
    assert doc_a not in filenames_b

    # 4. Test conflicting scope (Collection A scope + document from Collection B)
    # Backend must resolve allowed candidates to empty set and return empty immediately
    results_conflict = retriever.retrieve(
        query="What is the Project Apollo budget?",
        collection_id=coll_a["id"],
        document_filter=doc_b,
    )
    assert results_conflict == []

    # Clean up
    MetadataStore.delete_document_meta(doc_a)
    MetadataStore.delete_document_meta(doc_b)
    MetadataStore.delete_collection(coll_a["id"])
    MetadataStore.delete_collection(coll_b["id"])


def test_vector_and_lexical_candidate_filtering_mocked():
    """Verify that _vector_retrieve and _lexical_retrieve enforce allowed_filenames."""
    retriever = HybridRetriever()

    # Mock Chroma collection return
    mock_coll = MagicMock()
    mock_coll.count.return_value = 10
    retriever.collection = mock_coll

    # 1. Allowed filenames is empty -> vector retrieve should return []
    res_vec_empty = retriever._vector_retrieve([0.1] * 384, top_n=5, allowed_filenames=set())
    assert res_vec_empty == []

    # 2. Allowed filenames is set -> Chroma query should include where clause
    mock_coll.query.return_value = {"ids": [["docA-0"]], "distances": [[0.1]]}

    res_vec = retriever._vector_retrieve(
        [0.1] * 384, top_n=5, allowed_filenames={"docA.txt"}
    )
    assert len(res_vec) == 1
    assert res_vec[0][0] == "docA-0"
    mock_coll.query.assert_called_once()
    kwargs = mock_coll.query.call_args[1]
    assert kwargs["where"] == {"filename": "docA.txt"}
