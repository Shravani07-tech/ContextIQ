# api/routers/compare.py
#
# POST /compare -- Grounded document comparison endpoint.
# Accepts CompareRequest body containing filenames, optional question, and
# optional collection_id, returning a CompareResponse containing structured
# comparative findings and source citations.

import logging

from fastapi import APIRouter, HTTPException

from api.schemas import CompareRequest, CompareResponse
from comparison_service import ComparisonService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["compare"])


@router.post(
    "/compare",
    response_model=CompareResponse,
    summary="Compare two or more selected documents",
    responses={
        400: {"description": "Invalid filenames or missing documents"},
        403: {"description": "Requested document outside active collection scope"},
        503: {"description": "The language model is unreachable"},
    },
)
def compare(body: CompareRequest) -> CompareResponse:
    """
    Compare selected documents with scope enforcement and grounded evidence retrieval.
    """
    service = ComparisonService()
    try:
        result = service.compare_documents(
            filenames=body.filenames,
            question=body.question,
            collection_id=body.collection_id,
        )
        return CompareResponse(**result)
    except PermissionError as e:
        logger.warning(f"Comparison permission rejected: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        logger.warning(f"Comparison request error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Comparison execution failed")
        raise
