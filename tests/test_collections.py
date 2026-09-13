# tests/test_collections.py
# Unit tests for MetadataStore, Collection CRUD, and document assignment.

import pytest
from metadata_store import MetadataStore


def test_collection_crud(tmp_path):
    # Create Collection
    coll1 = MetadataStore.create_collection(
        name="  Research Notes  ",
        description="Market research documents",
        color="#EF4444",
        icon="book",
    )
    assert coll1["name"] == "Research Notes"
    assert coll1["description"] == "Market research documents"
    assert coll1["color"] == "#EF4444"
    assert coll1["icon"] == "book"

    coll_id = coll1["id"]

    # Read Collection
    fetched = MetadataStore.get_collection(coll_id)
    assert fetched is not None
    assert fetched["name"] == "Research Notes"

    # List Collections
    colls = MetadataStore.list_collections()
    assert any(c["id"] == coll_id for c in colls)

    # Update Collection
    updated = MetadataStore.update_collection(
        collection_id=coll_id,
        name="Updated Research",
        description="Updated description",
    )
    assert updated is not None
    assert updated["name"] == "Updated Research"
    assert updated["description"] == "Updated description"

    # Safe Delete Collection
    # First, link a document to this collection
    MetadataStore.upsert_document(
        filename="report.pdf",
        file_type="pdf",
        file_size=1024,
        collection_id=coll_id,
    )
    doc_before = MetadataStore.get_document("report.pdf")
    assert doc_before is not None
    assert doc_before["collection_id"] == coll_id

    # Delete collection
    deleted_status = MetadataStore.delete_collection(coll_id)
    assert deleted_status is True
    assert MetadataStore.get_collection(coll_id) is None

    # Verify document reverts to Uncategorized (collection_id = None)
    doc_after = MetadataStore.get_document("report.pdf")
    assert doc_after is not None
    assert doc_after["collection_id"] is None


def test_document_move():
    collA = MetadataStore.create_collection("Collection A")
    collB = MetadataStore.create_collection("Collection B")

    MetadataStore.upsert_document("paper.pdf", file_type="pdf", collection_id=collA["id"])
    doc = MetadataStore.get_document("paper.pdf")
    assert doc["collection_id"] == collA["id"]
    assert doc["collection_name"] == "Collection A"

    # Move to Collection B without re-indexing
    moved = MetadataStore.set_document_collection("paper.pdf", collB["id"])
    assert moved is True

    doc_moved = MetadataStore.get_document("paper.pdf")
    assert doc_moved["collection_id"] == collB["id"]
    assert doc_moved["collection_name"] == "Collection B"

    # Move to Uncategorized
    MetadataStore.set_document_collection("paper.pdf", None)
    doc_uncat = MetadataStore.get_document("paper.pdf")
    assert doc_uncat["collection_id"] is None
    assert doc_uncat["collection_name"] is None
