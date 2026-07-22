# api/routers/documents.py
#
# Document lifecycle endpoints:
#   POST /upload    -> stage files into data/ (no processing yet)
#   POST /index     -> run the ingestion pipeline over staged files
#   GET  /documents -> list what the vector database currently holds
#
# Upload and index are deliberately SEPARATE endpoints, mirroring the
# UI flow where uploading only stages files and nothing is processed
# until the user explicitly indexes — and matching how a future
# frontend will want to show distinct progress for each step.

from fastapi import APIRouter, UploadFile

from api.deps import DocumentServiceDep
from api.schemas import (
    DeleteDocumentResponse,
    DocumentsResponse,
    FileResult,
    IndexRequest,
    IndexResponse,
    UploadResponse,
)
from config import MAX_UPLOAD_MB
from vector_store import get_stored_filenames, get_vector_count

router = APIRouter(tags=["documents"])

MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Stage PDF/TXT files into the document folder",
)
def upload(files: list[UploadFile], docs: DocumentServiceDep) -> UploadResponse:
    """
    Save uploaded PDF/TXT files into the data/ folder.

    Outcomes are reported per file (unsupported types become an error
    entry rather than failing the whole request), so a mixed batch
    behaves predictably.

    Size enforcement happens HERE, server-side: the client's own
    25 MB check is fast feedback only. Each file is read with a hard
    cap (limit + 1 byte), so an oversized — or maliciously unbounded —
    stream can never exhaust memory or disk: it is rejected the
    moment it crosses the limit, and nothing is written.
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
            safe_name = docs.save_upload(f.filename or "", content)
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

    With no body (or null filenames) every supported file in data/ is
    (re)indexed — the API equivalent of `python ingest.py`. With a
    filenames list, only those files are processed.
    """
    filenames = body.filenames if body is not None else None
    results = docs.index_files(filenames)
    return IndexResponse(
        files=[FileResult(**r) for r in results],
        vector_count=get_vector_count(),
    )


@router.get(
    "/documents",
    response_model=DocumentsResponse,
    summary="List indexed documents",
)
def documents() -> DocumentsResponse:
    """Distinct source filenames currently in the vector database."""
    return DocumentsResponse(documents=get_stored_filenames())


@router.delete(
    "/documents/{filename}",
    response_model=DeleteDocumentResponse,
    summary="Delete one document (vectors + its file on disk)",
)
def delete_one(filename: str, docs: DocumentServiceDep) -> DeleteDocumentResponse:
    """
    Remove a single document's vectors from the knowledge base and
    its file from data/. Unlike DELETE /database, every other
    document is untouched. Deleting an unknown filename is a no-op
    (200, unchanged count) rather than a 404 — same idempotent policy
    DELETE /database already uses.
    """
    count = docs.delete_document(filename)
    return DeleteDocumentResponse(
        filename=filename, status="deleted", vector_count=count
    )
