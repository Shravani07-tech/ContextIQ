# api/routers/evidence.py
#
# POST /evidence/assess -- check one statement against the documents in
# scope and return a transparent, rule-based evidence rating (C8). The
# same assessment is attached automatically to chat answers.

from fastapi import APIRouter, HTTPException

from api.deps import get_rag_service
from api.schemas.insights import EvidenceAssessRequest, EvidenceAssessResponse
from evidence_service import check_claim

router = APIRouter(tags=["analysis"])


@router.post(
    "/evidence/assess",
    response_model=EvidenceAssessResponse,
    summary="Rate how well your documents support a statement",
    responses={
        400: {"description": "Unknown collection or document"},
        403: {"description": "Document outside the selected collection"},
    },
)
def assess(body: EvidenceAssessRequest) -> EvidenceAssessResponse:
    try:
        result = check_claim(
            body.claim,
            retriever=get_rag_service().retriever,
            collection_id=body.collection_id,
            filenames=body.filenames,
            check_contradictions=body.check_contradictions,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return EvidenceAssessResponse(**result)
