# api/main.py
#
# FastAPI application assembly: lifespan warm-up, CORS for the future
# Next.js dev server, and router mounting. Run from the project root:
#
#     uvicorn api.main:app --port 8000
#
# Interactive docs: http://localhost:8000/docs

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import chat, documents, system
from api.services import rag_service

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Load the expensive singletons (embedding model, LLM client) once
    at startup, so the first user request is fast instead of paying a
    multi-second cold start.
    """
    rag_service.warm_up()
    yield


app = FastAPI(
    title="ContextIQ API",
    description="Private AI-Powered Document Intelligence — REST API",
    version="1.5.0",
    lifespan=lifespan,
)

# The Next.js dev server (v1.5 frontend) will call this API from a
# different origin; without CORS every browser fetch would fail.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(documents.router)
app.include_router(chat.router)
