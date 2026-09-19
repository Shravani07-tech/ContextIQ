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

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from api.deps import get_rag_service
from api.schemas.models import ReportExportRequest, ResearchRequest, ResearchResponse
from report_service import ResearchReportService

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


@router.post("/research/export")
async def export_research_report(body: ReportExportRequest) -> Response:
    """
    Generate and download a research report in Markdown, PDF, or Plain Text format.
    """
    fmt = (body.format or "markdown").lower().strip()
    payload = body.model_dump()

    svc = ResearchReportService()

    try:
        if fmt == "pdf":
            pdf_bytes = svc.generate_pdf(payload)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": 'attachment; filename="contextiq-research-report.pdf"'
                },
            )
        elif fmt in ("txt", "text", "plain"):
            txt_content = svc.generate_txt(payload)
            return Response(
                content=txt_content,
                media_type="text/plain; charset=utf-8",
                headers={
                    "Content-Disposition": 'attachment; filename="contextiq-research-report.txt"'
                },
            )
        else:
            md_content = svc.generate_markdown(payload)
            return Response(
                content=md_content,
                media_type="text/markdown; charset=utf-8",
                headers={
                    "Content-Disposition": 'attachment; filename="contextiq-research-report.md"'
                },
            )
    except Exception as e:
        logger.exception("Failed to generate export report")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

