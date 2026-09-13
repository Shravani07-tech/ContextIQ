# api/routers/documents.py
#
# Document lifecycle endpoints:
#   POST /upload    -> stage files into data/ (no processing yet)
#   POST /index     -> run the ingestion pipeline over staged files
#   GET  /documents -> list what the vector database currently holds
#   PATCH /documents/{filename} -> update collection assignment
#   POST /documents/{filename}/tags -> add tag to document
#   DELETE /documents/{filename}/tags/{tag} -> remove tag from document
#   GET /tags       -> list all system tags
#   DELETE /documents/{filename} -> delete one document

from fastapi import APIRouter, HTTPException, UploadFile

from api.deps import DocumentServiceDep
from api.schemas import (
    DeleteDocumentResponse,
    DocumentDetail,
    DocumentListResponse,
    DocumentMoveRequest,
    DocumentsResponse,
    FileResult,
    IndexRequest,
    IndexResponse,
    TagActionResponse,
    TagAddRequest,
    TagListResponse,
    UploadResponse,
)
from config import MAX_UPLOAD_MB
from metadata_store import MetadataStore
from vector_store import get_stored_filenames, get_vector_count

router = APIRouter(tags=["documents"])

MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Stage PDF/TXT files into the document folder",
)
def upload(
    files: list[UploadFile],
    docs: DocumentServiceDep,
    collection_id: str | None = None,
) -> UploadResponse:
    """
    Save uploaded files into the data/ folder.
    Optionally assigns uploaded files directly to a target collection_id.
    """
    results: list[FileResult] = []
    for f in files:
        name = f.filename or "?"

        content = f.file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            results.append(
                FileResult(
                    filename=name,
                    status="error",
                    error=f"File exceeds the {MAX_UPLOAD_MB} MB limit",
                )
            )
            continue
        if len(content) == 0:
            results.append(
                FileResult(filename=name, status="error", error="File is empty")
            )
            continue

        try:
            safe_name = docs.save_upload(
                f.filename or "", content, collection_id=collection_id
            )
            results.append(FileResult(filename=safe_name, status="saved"))
        except ValueError as e:
            results.append(
                FileResult(filename=name, status="error", error=str(e))
            )
    return UploadResponse(files=results)


@router.post(
    "/index",
    response_model=IndexResponse,
    summary="Index staged files into the vector database",
)
def index(
    docs: DocumentServiceDep, body: IndexRequest | None = None
) -> IndexResponse:
    """
    Index staged files through the existing pipeline.
    """
    filenames = body.filenames if body is not None else None
    results = docs.index_files(filenames)
    return IndexResponse(
        files=[FileResult(**r) for r in results],
        vector_count=get_vector_count(),
    )


@router.get(
    "/documents",
    response_model=DocumentsResponse | DocumentListResponse,
    summary="List indexed documents",
)
def documents(
    collection_id: str | None = None,
    tag: str | None = None,
    detail: bool = False,
) -> DocumentsResponse | DocumentListResponse:
    """
    List documents currently indexed, optionally filtered by collection_id or tag.
    If detail=True, returns rich metadata (DocumentDetail list).
    If detail=False (default), returns simple list of filenames for backward compatibility.
    """
    if collection_id or tag or detail:
        doc_metas = MetadataStore.list_documents(
            collection_id=collection_id, tag=tag
        )
        if detail:
            return DocumentListResponse(
                documents=[DocumentDetail(**d) for d in doc_metas]
            )
        else:
            return DocumentsResponse(documents=[d["filename"] for d in doc_metas])

    return DocumentsResponse(documents=get_stored_filenames())


@router.get(
    "/documents/{filename}",
    response_model=DocumentDetail,
    summary="Get document details by filename",
)
def get_document_details(filename: str) -> DocumentDetail:
    """Get metadata, collection info, and tags for a specific document."""
    doc = MetadataStore.get_document(filename)
    if not doc:
        if filename in get_stored_filenames():
            ext = filename.split(".")[-1] if "." in filename else "txt"
            doc = MetadataStore.upsert_document(filename=filename, file_type=ext)
        else:
            raise HTTPException(
                status_code=404, detail=f"Document '{filename}' not found"
            )
    return DocumentDetail(**doc)


@router.patch(
    "/documents/{filename}",
    response_model=DocumentDetail,
    summary="Assign or move document to a collection",
)
def update_document(
    filename: str, body: DocumentMoveRequest
) -> DocumentDetail:
    """Assign document to a collection or move it to Uncategorized (null)."""
    doc = MetadataStore.get_document(filename)
    if not doc:
        if filename in get_stored_filenames():
            ext = filename.split(".")[-1] if "." in filename else "txt"
            doc = MetadataStore.upsert_document(filename=filename, file_type=ext)
        else:
            raise HTTPException(
                status_code=404, detail=f"Document '{filename}' not found"
            )

    try:
        updated = MetadataStore.set_document_collection(
            filename=filename, collection_id=body.collection_id
        )
        if not updated:
            raise HTTPException(
                status_code=404, detail=f"Document '{filename}' not found"
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    refreshed = MetadataStore.get_document(filename)
    return DocumentDetail(**refreshed)  # type: ignore


@router.post(
    "/documents/{filename}/tags",
    response_model=TagActionResponse,
    summary="Add a tag to a document",
)
def add_tag(filename: str, body: TagAddRequest) -> TagActionResponse:
    """Add a normalized tag to a document."""
    doc = MetadataStore.get_document(filename)
    if not doc:
        if filename in get_stored_filenames():
            ext = filename.split(".")[-1] if "." in filename else "txt"
            doc = MetadataStore.upsert_document(filename=filename, file_type=ext)
        else:
            raise HTTPException(
                status_code=404, detail=f"Document '{filename}' not found"
            )

    try:
        updated_tags = MetadataStore.add_document_tag(filename, body.tag)
        return TagActionResponse(filename=filename, tags=updated_tags)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/documents/{filename}/tags/{tag}",
    response_model=TagActionResponse,
    summary="Remove a tag from a document",
)
def remove_tag(filename: str, tag: str) -> TagActionResponse:
    """Remove a tag from a document."""
    doc = MetadataStore.get_document(filename)
    if not doc:
        raise HTTPException(
            status_code=404, detail=f"Document '{filename}' not found"
        )

    updated_tags = MetadataStore.remove_document_tag(filename, tag)
    return TagActionResponse(filename=filename, tags=updated_tags)


@router.get(
    "/tags",
    response_model=TagListResponse,
    summary="List all system tags",
)
def list_tags() -> TagListResponse:
    """List all unique document tags in the workspace."""
    tags = MetadataStore.list_all_tags()
    return TagListResponse(tags=tags)


@router.delete(
    "/documents/{filename}",
    response_model=DeleteDocumentResponse,
    summary="Delete one document (vectors + its file on disk)",
)
def delete_one(filename: str, docs: DocumentServiceDep) -> DeleteDocumentResponse:
    """
    Remove a single document's vectors from the knowledge base, metadata from SQLite,
    and its file from data/.
    """
    count = docs.delete_document(filename)
    return DeleteDocumentResponse(
        filename=filename, status="deleted", vector_count=count
    )
