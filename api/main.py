# api/main.py
#
# FastAPI application assembly: lifespan warm-up, CORS (origins from
# config/env), global exception handlers, request logging, and router
# mounting. Run from the project root:
#
#     uvicorn api.main:app --port 8000
#
# Interactive docs: http://localhost:8000/docs

import logging
import time
from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.deps import get_rag_service
from api.routers import chat, documents, system
from config import CORS_ORIGINS

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Section descriptions shown in the interactive /docs UI.
OPENAPI_TAGS = [
    {"name": "chat", "description": "Grounded question answering with source citations."},
    {"name": "documents", "description": "Upload, index, and list knowledge-base documents."},
    {"name": "system", "description": "Health, status, and database administration."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Build the expensive singletons (embedding model, LLM client) once
    at startup, so the first user request is fast instead of paying a
    multi-second cold start.
    """
    get_rag_service()
    yield


app = FastAPI(
    title="ContextIQ API",
    description=(
        "Private AI-Powered Document Intelligence — REST API.\n\n"
        "Upload PDF/TXT documents, index them into a local vector "
        "database, and ask questions answered strictly from their "
        "content, with per-answer source citations."
    ),
    version="1.5.0",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

# The Next.js dev server (v1.5 frontend) calls this API from a
# different origin; without CORS every browser fetch would fail.
# Origins come from config.py (CONTEXTIQ_CORS_ORIGINS env var).
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """One structured log line per request: method, path, status, ms."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %d (%.0f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.exception_handler(requests.RequestException)
async def ollama_unreachable(request: Request, exc: requests.RequestException):
    """
    Any unhandled outbound-HTTP failure (in practice: Ollama down)
    becomes a 503 — temporary and retryable — instead of a generic
    500. The stack trace goes to the server log, never the client.
    """
    logger.exception("Outbound request failed while handling %s", request.url.path)
    return JSONResponse(
        status_code=503,
        content={"detail": "The language model is unreachable. Is Ollama running?"},
    )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    """
    Last-resort handler: log the full traceback server-side, return a
    clean, detail-free 500 so internals never leak into responses.
    """
    logger.exception("Unhandled error while handling %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
    )


app.include_router(system.router)
app.include_router(documents.router)
app.include_router(chat.router)
