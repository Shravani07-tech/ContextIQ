# api/services/rag_service.py
#
# Injectable service wrapping the two expensive backend objects — the
# Retriever (embedding model + DB handle) and the LLM client. All
# retrieval/generation logic stays in the untouched root modules;
# this class only owns their lifecycle.
#
# Instantiated exactly once per process via api.deps.get_rag_service
# (lru_cache singleton) and warmed at startup by the lifespan hook so
# no user request ever pays the multi-second model cold start.

import logging

from llm import LLM
from rag import Retriever, answer_question
from vector_store import get_collection

logger = logging.getLogger(__name__)

# How much of a cited chunk the API returns as preview text — enough
# to judge relevance at a glance without shipping whole chunks.
PREVIEW_CHARS = 320


class RagService:
    """Owns the shared Retriever + LLM and answers questions with them."""

    def __init__(self) -> None:
        logger.info("Building RagService (loads embedding model)...")
        self.retriever = Retriever()
        self.llm = LLM()

    def ask(self, question: str) -> dict:
        """
        Answer one question via the existing full RAG pipeline, then
        enrich each cited source with a preview snippet of its chunk.

        answer_question() deliberately returns source METADATA only;
        the preview text is fetched here, at the API layer, by chunk
        id — so the core pipeline stays byte-identical while the API
        can power expandable source previews in the UI.
        """
        result = answer_question(question, self.retriever, self.llm)

        ids = [source["chunk_id"] for source in result["sources"]]
        if ids:
            records = self.retriever.collection.get(
                ids=ids, include=["documents"]
            )
            texts = dict(zip(records["ids"], records["documents"]))
            for source in result["sources"]:
                text = texts.get(source["chunk_id"])
                if text:
                    source["preview"] = text[:PREVIEW_CHARS] + (
                        "…" if len(text) > PREVIEW_CHARS else ""
                    )

        return result

    def refresh_collection(self) -> None:
        """
        Re-point the cached Retriever at a fresh Chroma collection.

        Needed after DELETE /database: clearing deletes the collection
        the Retriever is holding, so its handle goes stale. Re-fetching
        just the collection (rather than rebuilding the whole service)
        avoids a needless embedding-model reload.
        """
        self.retriever.collection = get_collection()
