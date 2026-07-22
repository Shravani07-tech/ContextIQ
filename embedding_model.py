# embedding_model.py
#
# Process-wide singleton for the sentence-transformers embedding
# model. ingest.py (chunk embedding) and rag.py (query embedding)
# MUST share the exact same loaded instance — not just the same
# model name — so one process never holds two ~130MB copies in
# memory. Previously each module built its own: ingest.py cached one
# locally, and Retriever constructed a second, independent one.
#
# A lock guards first construction so two threads racing to embed at
# once (e.g. an upload and a chat request in the API's threadpool)
# can't both pass the None-check and load the model twice.

import logging
import threading

from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL_NAME

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Return the shared embedding model, loading it on first use."""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                logger.info("Loading embedding model '%s'...", EMBEDDING_MODEL_NAME)
                _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model
