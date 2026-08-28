# reranker.py
#
# Optional cross-encoder reranking layer for ContextIQ.
#
# Uses the sentence-transformers cross-encoder API to score
# (query, passage) pairs directly, rather than comparing independent
# query and passage embeddings. Cross-encoders produce better relevance
# scores at the cost of latency proportional to the number of candidates —
# which is why they run AFTER retrieval narrows the pool (typically 8-12
# candidates), not across the whole corpus.
#
# Model: cross-encoder/ms-marco-MiniLM-L-2-v2
#   - ~22MB on disk, fast on CPU (~40ms/passage)
#   - Trained on MS MARCO passage ranking (question-answer pairs)
#   - Good general-domain reranking quality
#
# FALLBACK POLICY (documented honestly):
#   If the cross-encoder model cannot be loaded (missing dependency,
#   out of memory, disk full), a warning is logged and the module
#   falls back to SIMILARITY ORDERING — the same similarity scores
#   the hybrid retrieval step already computed. This is NOT neural
#   reranking; it is a graceful degradation that avoids breaking the
#   pipeline. The boolean RERANKING_ENABLED tells callers which mode
#   is active, so it can be logged and displayed.
#
# The model is loaded ONCE on first call (lazy) and cached at module
# level. Subsequent calls never reload it — avoiding the multi-second
# cold-start on every query that would otherwise make reranking unusable
# on CPU-only machines.

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Module-level cache — None means "not yet attempted".
# False means "attempted and failed; use fallback".
_cross_encoder: object | None | bool = None  # None = not tried; False = failed

# Public flag: True when the neural cross-encoder is active.
RERANKING_ENABLED: bool = False

# Public variable exposing the actual mode of the reranker.
# Values: "NEURAL_RERANKER" or "LIGHTWEIGHT_FALLBACK"
RERANKER_MODE: str = "LIGHTWEIGHT_FALLBACK"


def _get_cross_encoder() -> object | None:
    """
    Load and cache the cross-encoder model.

    Returns the CrossEncoder instance on success, None on failure.
    Never raises — failures are caught and logged.
    """
    global _cross_encoder, RERANKING_ENABLED, RERANKER_MODE

    if _cross_encoder is False:
        return None  # Already tried and failed.
    if _cross_encoder is not None:
        return _cross_encoder  # Already loaded successfully.

    # First call: attempt to load.
    try:
        from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]
        import torch
        torch.set_num_threads(1)
        logger.info(
            "Loading cross-encoder reranker (cross-encoder/ms-marco-MiniLM-L-2-v2)..."
        )
        model = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-2-v2",
            # Limit to a single CPU thread per inference call to avoid
            # CPU contention with the embedding model and Ollama.
            device="cpu",
        )
        _cross_encoder = model
        RERANKING_ENABLED = True
        RERANKER_MODE = "NEURAL_RERANKER"
        logger.info("Cross-encoder reranker loaded successfully. Mode: NEURAL_RERANKER")
        return model
    except Exception:
        logger.warning(
            "Cross-encoder reranker could not be loaded — "
            "falling back to similarity ordering. "
            "Mode: LIGHTWEIGHT_FALLBACK. "
            "Install sentence-transformers to enable neural reranking.",
            exc_info=True,
        )
        _cross_encoder = False
        RERANKING_ENABLED = False
        RERANKER_MODE = "LIGHTWEIGHT_FALLBACK"
        return None


def rerank(
    query: str,
    chunks: list[dict],
    top_k: int,
) -> list[dict]:
    """
    Rerank retrieval candidates and return the top_k most relevant.

    Args:
        query:   The user's question (raw, no prefix).
        chunks:  Candidate chunks from hybrid retrieval, each a dict with
                 at least {"chunk_id", "chunk_text", "similarity", ...}.
        top_k:   How many chunks to return.

    Returns a new list of up to top_k chunks, sorted by descending
    relevance. The cross-encoder score (when active) is stored in the
    "rerank_score" key of each chunk dict so callers can inspect it.

    Fallback: if the cross-encoder is unavailable, chunks are sorted by
    their existing "similarity" field and the top_k are returned — this
    preserves the hybrid-retrieval ordering (vector-similarity-based),
    which is still substantially better than no retrieval.
    """
    if not chunks:
        return []

    # Limit how many candidates we actually score through the cross-encoder.
    # Scoring 30+ pairs on CPU takes 1-2 seconds; 12 pairs take ~200ms.
    # The hybrid retrieval pool is typically top_k*2 to top_k*3, so this
    # cap is rarely hit in normal usage.
    MAX_CANDIDATES = min(len(chunks), top_k * 3)
    candidates = chunks[:MAX_CANDIDATES]

    model = _get_cross_encoder()

    if model is not None:
        # Neural reranking path.
        pairs = [(query, c["chunk_text"]) for c in candidates]
        try:
            scores = model.predict(pairs, show_progress_bar=False)
        except Exception:
            logger.warning("Cross-encoder prediction failed; using similarity fallback.")
            scores = None

        if scores is not None:
            for chunk, score in zip(candidates, scores):
                chunk["rerank_score"] = float(score)
            candidates.sort(key=lambda c: -c["rerank_score"])
            return candidates[:top_k]

    # Similarity fallback.
    candidates.sort(key=lambda c: -c["similarity"])
    return candidates[:top_k]
