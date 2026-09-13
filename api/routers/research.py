# api/routers/research.py
#
# Research Mode API endpoints.
#
# POST /research        — blocking, structured JSON synthesis
# POST /research/stream — streaming SSE synthesis
#
# Both endpoints call the research.py pipeline which retrieves across
# ALL indexed documents (no document_filter) and synthesizes with a
# single structured LLM call.

import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.deps import get_rag_service
from api.schemas.models import ResearchRequest, ResearchResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/research", response_model=ResearchResponse)
async def research(body: ResearchRequest) -> ResearchResponse:
    """
    Synthesize an answer across scoped or all indexed documents.
    """
    from research import research_question

    rag_service = get_rag_service()
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: research_question(
            body.question,
            retriever=rag_service.retriever,
            llm=rag_service.llm,
            collection_id=body.collection_id,
            tag=body.tag,
            tags=body.tags,
        ),
    )

    sources = rag_service.enrich_sources(result.get("sources", []))
    return ResearchResponse(
        answer=result["answer"],
        sources=sources,
        doc_count=result.get("doc_count", 0),
    )


@router.post("/research/stream")
async def research_stream(body: ResearchRequest) -> StreamingResponse:
    """
    Streaming SSE variant of the Research Mode endpoint.
    """
    from research import research_question_stream

    rag_service = get_rag_service()

    def _iter():
        try:
            for event in research_question_stream(
                body.question,
                retriever=rag_service.retriever,
                llm=rag_service.llm,
                collection_id=body.collection_id,
                tag=body.tag,
                tags=body.tags,
            ):
                if event.get("type") == "sources":
                    enriched = rag_service.enrich_sources(event.get("sources", []))
                    event = {**event, "sources": enriched}
                yield f"data: {json.dumps(event)}\n\n"
            yield f'data: {json.dumps({"type": "done"})}\n\n'

        except Exception:
            logger.exception("Research stream error")
            yield f'data: {json.dumps({"type": "error", "detail": "Research synthesis failed."})}\n\n'

    return StreamingResponse(_iter(), media_type="text/event-stream")
