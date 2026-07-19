# api/routers/system.py
#
# Operational endpoints:
#   GET    /health   -> liveness + dependency reachability
#   GET    /status   -> knowledge-base status + pipeline settings
#   DELETE /database -> clear every vector (files in data/ are kept)

import logging

import requests
from fastapi import APIRouter

from api.deps import RagServiceDep
from api.schemas import ClearDatabaseResponse, HealthResponse, StatusResponse
from config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_MODEL_NAME,
    LLM_MODEL_NAME,
    OLLAMA_BASE_URL,
    TOP_K,
)
from vector_store import clear_database, get_stored_filenames, get_vector_count

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness and dependency reachability",
)
def health() -> HealthResponse:
    """
    Liveness plus reachability of the two external dependencies.

    Chroma is checked with a real count() call; Ollama with a cheap
    GET to its tags endpoint (3s timeout so a down server degrades
    the health report quickly instead of hanging it).
    """
    try:
        get_vector_count()
        chroma_ok = True
    except Exception:
        logger.exception("Chroma health check failed")
        chroma_ok = False

    try:
        requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3).raise_for_status()
        ollama_ok = True
    except requests.RequestException:
        ollama_ok = False

    return HealthResponse(
        status="ok" if (chroma_ok and ollama_ok) else "degraded",
        chroma=chroma_ok,
        ollama=ollama_ok,
    )


@router.get(
    "/status",
    response_model=StatusResponse,
    summary="Knowledge-base status and pipeline settings",
)
def status() -> StatusResponse:
    """Everything the sidebar shows today: counts, files, settings."""
    documents = get_stored_filenames()
    return StatusResponse(
        vector_count=get_vector_count(),
        document_count=len(documents),
        documents=documents,
        embedding_model=EMBEDDING_MODEL_NAME,
        llm_model=LLM_MODEL_NAME,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        top_k=TOP_K,
    )


@router.delete(
    "/database",
    response_model=ClearDatabaseResponse,
    summary="Delete every vector from the knowledge base",
)
def clear(rag: RagServiceDep) -> ClearDatabaseResponse:
    """
    Delete every vector from the knowledge base.

    Files in data/ are intentionally kept (same policy as the UI's
    Clear button) — POST /index can rebuild the database from them.
    The injected RagService's collection handle is refreshed because
    clearing deletes the collection it was holding.
    """
    clear_database()
    rag.refresh_collection()
    return ClearDatabaseResponse(status="cleared", vector_count=get_vector_count())
