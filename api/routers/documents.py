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
    DocumentsResponse,
    FileResult,
    IndexRequest,
    IndexResponse,
    UploadResponse,
)
from vector_store import get_stored_filenames, get_vector_count

router = APIRouter(tags=["documents"])


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
    """
    results: list[FileResult] = []
    for f in files:
        try:
            safe_name = docs.save_upload(f.filename or "", f.file.read())
            results.append(FileResult(filename=safe_name, status="saved"))
        except ValueError as e:
            results.append(
                FileResult(filename=f.filename or "?", status="error", error=str(e))
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
