# tests/test_scoped_rag.py

from fastapi.testclient import TestClient
import pytest

from api.main import app
from api.schemas import ChatRequest, ResearchRequest
from metadata_store import MetadataStore

client = TestClient(app)


def test_schema_scope_fields():
    chat_req = ChatRequest(
        question="What is the budget?",
        collection_id="coll-123",
        tag="finance",
        tags=["finance", "important"],
    )
    assert chat_req.collection_id == "coll-123"
    assert chat_req.tag == "finance"
    assert chat_req.tags == ["finance", "important"]

    res_req = ResearchRequest(
        question="Summarize findings",
        collection_id="coll-456",
        tag="research",
    )
    assert res_req.collection_id == "coll-456"
    assert res_req.tag == "research"


def test_empty_collection_chat_and_research_scoped_fallback():
    # 1. Create an empty collection
    coll = MetadataStore.create_collection("Empty Scope Collection")
    coll_id = coll["id"]

    # 2. Chat query scoped to empty collection -> should return honest fallback without calling LLM
    r_chat = client.post(
        "/chat",
        json={"question": "What is the project budget?", "collection_id": coll_id},
    )
    assert r_chat.status_code == 200
    res_chat = r_chat.json()
    assert "don't know" in res_chat["answer"].lower()
    assert res_chat["sources"] == []

    # 3. Research query scoped to empty collection -> should return fallback synthesis
    r_res = client.post(
        "/research",
        json={"question": "Synthesize the strategy", "collection_id": coll_id},
    )
    assert r_res.status_code == 200
    res_data = r_res.json()
    assert "cannot synthesize" in res_data["answer"].lower()
    assert res_data["sources"] == []
    assert res_data["doc_count"] == 0

    # Clean up
    MetadataStore.delete_collection(coll_id)
