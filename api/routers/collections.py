# api/routers/collections.py
#
# REST API endpoints for Workspace Collections management in ContextIQ 2.0.

from fastapi import APIRouter, HTTPException, status

from api.schemas.models import (
    CollectionCreate,
    CollectionListResponse,
    CollectionResponse,
    CollectionUpdate,
)
from metadata_store import MetadataStore

router = APIRouter(prefix="/collections", tags=["collections"])


def _reject_duplicate_name(name: str, exclude_id: str | None = None) -> None:
    """Collection names are unique case-insensitively. Enforced here rather
    than with a UNIQUE index so databases that already contain duplicates
    keep working; existing duplicates are left for the user to resolve."""
    if MetadataStore.find_collection_by_name(name, exclude_id=exclude_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A collection named '{name.strip()}' already exists.",
        )


@router.post(
    "",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new collection",
    responses={409: {"description": "A collection with this name already exists"}},
)
def create_collection(body: CollectionCreate) -> CollectionResponse:
    """Create a new logical document collection."""
    _reject_duplicate_name(body.name)
    coll = MetadataStore.create_collection(
        name=body.name,
        description=body.description,
        color=body.color,
        icon=body.icon,
    )
    return CollectionResponse(**coll)


@router.get(
    "",
    response_model=CollectionListResponse,
    summary="List all collections",
)
def list_collections() -> CollectionListResponse:
    """List all available collections with document counts."""
    colls = MetadataStore.list_collections()
    return CollectionListResponse(
        collections=[CollectionResponse(**c) for c in colls]
    )


@router.get(
    "/{collection_id}",
    response_model=CollectionResponse,
    summary="Get collection details",
)
def get_collection(collection_id: str) -> CollectionResponse:
    """Retrieve details for a single collection."""
    coll = MetadataStore.get_collection(collection_id)
    if not coll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection '{collection_id}' not found",
        )
    return CollectionResponse(**coll)


@router.patch(
    "/{collection_id}",
    response_model=CollectionResponse,
    summary="Update collection details",
    responses={409: {"description": "A collection with this name already exists"}},
)
def update_collection(
    collection_id: str, body: CollectionUpdate
) -> CollectionResponse:
    """Update name, description, color, or icon for an existing collection."""
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(status_code=422, detail="Collection name must not be empty")
        _reject_duplicate_name(body.name, exclude_id=collection_id)
    coll = MetadataStore.update_collection(
        collection_id=collection_id,
        name=body.name,
        description=body.description,
        color=body.color,
        icon=body.icon,
    )
    if not coll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection '{collection_id}' not found",
        )
    return CollectionResponse(**coll)


@router.delete(
    "/{collection_id}",
    summary="Delete collection",
)
def delete_collection(collection_id: str) -> dict:
    """
    Delete a collection safely.
    Documents belonging to this collection revert to Uncategorized (collection_id = null).
    Vector embeddings and disk files remain completely intact.
    """
    success = MetadataStore.delete_collection(collection_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection '{collection_id}' not found",
        )
    return {"status": "deleted", "id": collection_id}
