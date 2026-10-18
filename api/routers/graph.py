# api/routers/graph.py
#
# Knowledge graph endpoints (C10):
#   POST /graph/build              extract entities/relations for a scope
#   GET  /graph                    nodes + edges for a scope
#   GET  /graph/entities/{id}      one entity with mentions and evidence
#
# Every read takes the same scope parameters and only returns facts from
# documents inside it; an entity that exists only outside the scope is a
# 404, so its existence is not revealed.

from fastapi import APIRouter, HTTPException, Query

from api.schemas.insights import (
    EntityDetailResponse,
    GraphBuildRequest,
    GraphBuildResponse,
    GraphResponse,
)
from graph_service import GraphService

router = APIRouter(tags=["analysis"])

_SCOPE_ERRORS = {
    400: {"description": "Unknown collection or document"},
    403: {"description": "Document outside the selected collection"},
}


def _scoped(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/graph/build", response_model=GraphBuildResponse, responses=_SCOPE_ERRORS,
             summary="Extract an evidence-linked graph for documents in scope")
def build_graph(body: GraphBuildRequest) -> GraphBuildResponse:
    result = _scoped(
        GraphService().build,
        collection_id=body.collection_id,
        filenames=body.filenames,
        force=body.force,
        use_llm=body.use_llm,
    )
    return GraphBuildResponse(**result)


@router.get("/graph", response_model=GraphResponse, responses=_SCOPE_ERRORS,
            summary="Graph nodes and edges for a scope")
def get_graph(
    collection_id: str | None = None,
    filenames: list[str] | None = Query(default=None, max_length=25),
    limit: int | None = Query(default=None, ge=1, le=500),
) -> GraphResponse:
    return GraphResponse(**_scoped(GraphService().get_graph, collection_id, filenames, limit))


@router.get("/graph/entities/{entity_id}", response_model=EntityDetailResponse,
            responses={**_SCOPE_ERRORS, 404: {"description": "Entity not found in this scope"}},
            summary="One entity with its mentions and evidence-linked relations")
def get_entity(
    entity_id: str,
    collection_id: str | None = None,
    filenames: list[str] | None = Query(default=None, max_length=25),
) -> EntityDetailResponse:
    detail = _scoped(GraphService().get_entity, entity_id, collection_id, filenames)
    if detail is None:
        raise HTTPException(status_code=404, detail="Entity not found in this scope.")
    return EntityDetailResponse(**detail)
