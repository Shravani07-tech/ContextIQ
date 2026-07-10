# api/services/rag_service.py
#
# Holds the two expensive objects — the Retriever (embedding model +
# DB handle) and the LLM client — as lazy process-wide singletons.
#
# This is the FastAPI equivalent of Streamlit's @st.cache_resource:
# without it, every /chat request would reload the multi-second
# SentenceTransformer from scratch (the app would work, just be
# catastrophically slow — the #1 risk called out in the migration
# plan). warm_up() is called from the app's lifespan hook so the
# first real user request doesn't pay the cold-start cost either.

import logging
import threading

from llm import LLM
from rag import Retriever, answer_question
from vector_store import get_collection

logger = logging.getLogger(__name__)

# Lock guards first-time construction when several requests race in
# the threadpool; after that, reads are cheap attribute lookups.
_lock = threading.Lock()
_retriever: Retriever | None = None
_llm: LLM | None = None


def get_retriever() -> Retriever:
    """Return the shared Retriever, building it on first use."""
    global _retriever
    if _retriever is None:
        with _lock:
            if _retriever is None:
                logger.info("Building Retriever (loads embedding model)...")
                _retriever = Retriever()
    return _retriever


def get_llm() -> LLM:
    """Return the shared LLM client, building it on first use."""
    global _llm
    if _llm is None:
        with _lock:
            if _llm is None:
                _llm = LLM()
    return _llm


def warm_up() -> None:
    """Eagerly build both singletons (called at server startup)."""
    get_retriever()
    get_llm()


def ask(question: str) -> dict:
    """Answer one question via the existing full RAG pipeline."""
    return answer_question(question, get_retriever(), get_llm())


def refresh_collection() -> None:
    """
    Re-point the cached Retriever at a fresh Chroma collection.

    Needed after DELETE /database: clearing deletes the collection the
    Retriever is holding, so its handle goes stale. Re-fetching just
    the collection (rather than rebuilding the whole Retriever) avoids
    a needless multi-second embedding-model reload.
    """
    if _retriever is not None:
        _retriever.collection = get_collection()
