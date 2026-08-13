# api/services/rag_service.py
#
# Injectable service wrapping the two expensive backend objects -- the
# Retriever (embedding model + DB handle) and the LLM client. All
# retrieval/generation logic stays in the untouched root modules;
# this class only owns their lifecycle.
#
# Instantiated exactly once per process via api.deps.get_rag_service
# (lru_cache singleton) and warmed at startup by the lifespan hook so
# no user request ever pays the multi-second model cold start.

import logging
from collections.abc import Iterator

from llm import LLM
from rag import Retriever, answer_question, answer_question_stream
from vector_store import get_collection

logger = logging.getLogger(__name__)

# How much of a cited chunk the API returns as preview text -- enough
# to judge relevance at a glance without shipping whole chunks.
PREVIEW_CHARS = 320


class RagService:
    """Owns the shared Retriever + LLM and answers questions with them."""

    def __init__(self) -> None:
        logger.info("Building RagService (loads embedding model)...")
        self.retriever = Retriever()
        self.llm = LLM()

    def ask(
        self,
        question: str,
        history: list[dict] | None = None,
        document_filter: str | None = None,
    ) -> dict:
        """
        Answer one question via the existing full RAG pipeline, then
        enrich each cited source with a preview snippet of its chunk.

        answer_question() deliberately returns source METADATA only;
        the preview text is fetched here, at the API layer, by chunk
        id -- so the core pipeline stays byte-identical while the API
        can power expandable source previews in the UI.

        Args:
            history:         Bounded conversation history (max 6 turns).
                             Sent to LLM; does NOT affect retrieval.
            document_filter: When set, restricts retrieval to this filename.
        """
        result = answer_question(
            question,
            self.retriever,
            self.llm,
            history=history,
            document_filter=document_filter,
        )
        self._enrich_sources(result["sources"])
        return result

    def _enrich_sources(self, sources: list[dict]) -> None:
        """Attach a preview snippet to each source, in place -- the
        same enrichment ask() does, factored out so the streaming
        path can apply it before the sources event goes out."""
        ids = [source["chunk_id"] for source in sources]
        if not ids:
            return
        records = self.retriever.collection.get(
            ids=ids, include=["documents", "metadatas"]
        )
        texts = dict(zip(records["ids"], records["documents"]))
        metas = dict(zip(records["ids"], records["metadatas"]))
        for source in sources:
            cid = source["chunk_id"]
            text = texts.get(cid)
            if text:
                source["preview"] = text[:PREVIEW_CHARS] + (
                    "\u2026" if len(text) > PREVIEW_CHARS else ""
                )
            # Enrich page/section from stored metadata if not already set
            meta = metas.get(cid, {})
            if source.get("page") is None and meta.get("page") is not None:
                source["page"] = meta["page"]
            if source.get("section") is None and meta.get("section") is not None:
                source["section"] = meta["section"]

    def ask_stream(
        self,
        question: str,
        history: list[dict] | None = None,
        document_filter: str | None = None,
    ) -> Iterator[dict]:
        """
        Streaming counterpart to ask(): same preview enrichment for
        sources, applied before the "sources" event is yielded rather
        than after the fact -- streaming sends sources to the client
        immediately, so enrichment can't happen retroactively.

        Args:
            history:         Bounded conversation history (max 6 turns).
            document_filter: Restrict retrieval to one document filename.
        """
        for event in answer_question_stream(
            question,
            self.retriever,
            self.llm,
            history=history,
            document_filter=document_filter,
        ):
            if event["type"] == "sources":
                self._enrich_sources(event["sources"])
            yield event

    def refresh_collection(self) -> None:
        """
        Re-point the cached Retriever at a fresh Chroma collection.

        Needed after DELETE /database: clearing deletes the collection
        the Retriever is holding, so its handle goes stale. Re-fetching
        just the collection (rather than rebuilding the whole service)
        avoids a needless embedding-model reload.
        """
        self.retriever.collection = get_collection()
