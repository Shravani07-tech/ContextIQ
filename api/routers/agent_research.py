# api/routers/agent_research.py
#
# Bounded agentic research (C11):
#   POST /research/agent         run to completion, return the result
#   POST /research/agent/stream  same run as Server-Sent Events:
#                                progress / plan / sources / token /
#                                result / done | error
#
# The scope is validated BEFORE the stream starts, so scope problems are
# real 400/403 responses. During streaming, a client disconnect (the UI's
# Stop button aborts the fetch) cancels the run between steps and between
# answer tokens; the orchestrator's generator is then closed, which also
# closes the in-flight Ollama request.

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from agentic_research import AgenticResearcher, CancelToken, ResearchLimits, run_to_completion
from api.deps import get_rag_service
from api.schemas.insights import AgentResearchRequest, AgentResearchResult
from scope import resolve_scope

logger = logging.getLogger(__name__)

router = APIRouter(tags=["research"])

_SCOPE_ERRORS = {
    400: {"description": "Unknown collection or document"},
    403: {"description": "Document outside the selected collection"},
}


def _prepare(body: AgentResearchRequest):
    try:
        scope = resolve_scope(collection_id=body.collection_id, filenames=body.filenames)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    limits = ResearchLimits()
    if body.max_subquestions:
        limits.max_subquestions = min(limits.max_subquestions, body.max_subquestions)
    rag = get_rag_service()
    return AgenticResearcher(rag.retriever, limits=limits), scope, rag


def _enrich(result: dict, rag) -> dict:
    try:
        rag.enrich_sources(result.get("sources", []))
    except Exception:
        logger.warning("Could not attach source previews", exc_info=True)
    return result


@router.post("/research/agent", response_model=AgentResearchResult, responses=_SCOPE_ERRORS,
             summary="Bounded multi-step research over the documents in scope")
def research_agent(body: AgentResearchRequest) -> AgentResearchResult:
    researcher, scope, rag = _prepare(body)
    result = run_to_completion(researcher, body.question, scope=scope)
    return AgentResearchResult(**_enrich(result, rag))


@router.post("/research/agent/stream", responses=_SCOPE_ERRORS,
             summary="Bounded multi-step research, streamed as Server-Sent Events")
async def research_agent_stream(body: AgentResearchRequest, request: Request) -> StreamingResponse:
    researcher, scope, rag = _prepare(body)
    cancel = CancelToken()
    events = researcher.run(body.question, scope=scope, cancel=cancel)
    sentinel = object()

    async def _iter():
        try:
            while True:
                if await request.is_disconnected():
                    cancel.cancel()
                    break
                event = await run_in_threadpool(next, events, sentinel)
                if event is sentinel:
                    break
                if event.get("type") == "sources":
                    event = {**event, "sources": rag.enrich_sources(event.get("sources", []))}
                elif event.get("type") == "result":
                    event = {**event, "result": _enrich(event["result"], rag)}
                yield f"data: {json.dumps(event)}\n\n"
            if not cancel.cancelled:
                yield f'data: {json.dumps({"type": "done"})}\n\n'
        except Exception:
            logger.exception("Agentic research stream failed")
            yield f'data: {json.dumps({"type": "error", "detail": "Research failed unexpectedly."})}\n\n'
        finally:
            cancel.cancel()
            await run_in_threadpool(events.close)

    return StreamingResponse(
        _iter(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
