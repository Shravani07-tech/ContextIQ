# tests/test_tags_and_metadata.py

from fastapi.testclient import TestClient
import pytest

from api.main import app
from metadata_store import MetadataStore

client = TestClient(app)


def test_tag_normalization_and_crud():
    # 1. Create a dummy collection and upsert a document
    coll = MetadataStore.create_collection("Tag Test Collection")
    coll_id = coll["id"]

    doc_name = "test_tag_doc.txt"
    MetadataStore.upsert_document(
        filename=doc_name,
        file_type="txt",
        file_size=100,
        chunk_count=2,
        collection_id=coll_id,
    )

    # 2. Add tag with spaces and uppercase -> should normalize to lowercase, trimmed
    r = client.post(f"/documents/{doc_name}/tags", json={"tag": "  Finance  "})
    assert r.status_code == 200
    assert "finance" in r.json()["tags"]

    # Add second tag
    r2 = client.post(f"/documents/{doc_name}/tags", json={"tag": "RESEARCH"})
    assert r2.status_code == 200
    assert set(r2.json()["tags"]) == {"finance", "research"}

    # Add duplicate tag -> should be deduplicated
    r3 = client.post(f"/documents/{doc_name}/tags", json={"tag": "finance"})
    assert r3.status_code == 200
    assert r3.json()["tags"].count("finance") == 1

    # 3. List system tags
    r_tags = client.get("/tags")
    assert r_tags.status_code == 200
    assert "finance" in r_tags.json()["tags"]
    assert "research" in r_tags.json()["tags"]

    # 4. Filter documents by tag
    r_filter = client.get("/documents", params={"tag": "finance", "detail": True})
    assert r_filter.status_code == 200
    docs = r_filter.json()["documents"]
    assert len(docs) >= 1
    assert any(d["filename"] == doc_name for d in docs)

    # Filter documents by non-existent tag
    r_empty = client.get(
        "/documents", params={"tag": "nonexistenttag", "detail": True}
    )
    assert r_empty.status_code == 200
    assert len(r_empty.json()["documents"]) == 0

    # 5. Remove tag
    r_del = client.delete(f"/documents/{doc_name}/tags/finance")
    assert r_del.status_code == 200
    assert "finance" not in r_del.json()["tags"]

    # Clean up
    MetadataStore.delete_document_meta(doc_name)
    MetadataStore.delete_collection(coll_id)


def test_document_move_and_upload_collection():
    # 1. Create two collections
    c1 = MetadataStore.create_collection("Coll Alpha")
    c2 = MetadataStore.create_collection("Coll Beta")

    doc_name = "test_move_doc.txt"
    MetadataStore.upsert_document(
        filename=doc_name, file_type="txt", collection_id=c1["id"]
    )

    # Verify initial collection assignment
    detail = client.get(f"/documents/{doc_name}").json()
    assert detail["collection_id"] == c1["id"]

    # 2. Move document to Coll Beta without re-indexing
    r_move = client.patch(
        f"/documents/{doc_name}", json={"collection_id": c2["id"]}
    )
    assert r_move.status_code == 200
    assert r_move.json()["collection_id"] == c2["id"]

    # 3. Move document to Uncategorized (null)
    r_uncat = client.patch(f"/documents/{doc_name}", json={"collection_id": None})
    assert r_uncat.status_code == 200
    assert r_uncat.json()["collection_id"] is None

    # 4. Attempt to move to non-existent collection -> 400 Bad Request
    r_invalid = client.patch(
        f"/documents/{doc_name}", json={"collection_id": "invalid-uuid-1234"}
    )
    assert r_invalid.status_code == 400

    # Clean up
    MetadataStore.delete_document_meta(doc_name)
    MetadataStore.delete_collection(c1["id"])
    MetadataStore.delete_collection(c2["id"])


def test_tag_validation_and_errors():
    # Empty tag -> 422
    r1 = client.post("/documents/test_move_doc.txt/tags", json={"tag": "   "})
    assert r1.status_code == 422

    # Oversized tag (> 50 chars) -> 422
    r2 = client.post(
        "/documents/test_move_doc.txt/tags", json={"tag": "a" * 51}
    )
    assert r2.status_code == 422

    # Non-existent document tag add -> 404
    r3 = client.post("/documents/ghost_doc.txt/tags", json={"tag": "valid"})
    assert r3.status_code == 404
