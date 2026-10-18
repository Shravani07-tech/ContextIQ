# api/routers/timeline.py
#
# POST /timeline -- source-grounded timeline for a collection or a set
# of selected documents (C7). Scope errors map to 400/403; an Ollama
# outage is not an error here because the service falls back to
# pattern-based extraction and reports that in `warnings`.

import logging

from fastapi import APIRouter, HTTPException

from api.deps import get_rag_service
from api.schemas.insights import TimelineRequest, TimelineResponse
from timeline_service import TimelineService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


@router.post(
    "/timeline",
    response_model=TimelineResponse,
    summary="Extract a chronological, source-linked timeline",
    responses={
        400: {"description": "Unknown collection or document"},
        403: {"description": "Document outside the selected collection"},
    },
)
def timeline(body: TimelineRequest) -> TimelineResponse:
    service = TimelineService(retriever=get_rag_service().retriever)
    try:
        result = service.build_timeline(
            collection_id=body.collection_id,
            filenames=body.filenames,
            focus=body.focus,
            max_events=body.max_events,
            use_llm=body.use_llm,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TimelineResponse(**result)
