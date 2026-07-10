# api/schemas/models.py
#
# Every request/response shape the API exposes, in one place. These
# mirror what the existing backend functions already return (e.g.
# ChatResponse matches rag.answer_question()'s dict exactly), so the
# service layer never has to reshape data — it just passes it through.

from pydantic import BaseModel, Field, field_validator


# --- chat -------------------------------------------------------------------


class ChatRequest(BaseModel):
    """A single question for the knowledge base."""

    question: str = Field(..., description="Natural-language question")

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        """Strip and reject empty/whitespace-only questions (same rule
        the Streamlit UI enforces) — FastAPI turns this into a 422."""
        v = v.strip()
        if not v:
            raise ValueError("question must not be empty")
        return v


class Source(BaseModel):
    """One retrieved chunk an answer was grounded on."""

    filename: str
    chunk_id: str
    similarity: float


class ChatResponse(BaseModel):
    """Grounded answer plus the sources it came from."""

    answer: str
    sources: list[Source]


# --- documents / ingestion ---------------------------------------------------


class FileResult(BaseModel):
    """Per-file outcome for upload and index operations — errors are
    reported per file so one bad PDF never hides the others' success
    (the same policy the ingestion pipeline itself follows)."""

    filename: str
    status: str  # "saved" | "indexed" | "error"
    chunks_indexed: int | None = None
    error: str | None = None


class UploadResponse(BaseModel):
    """Outcome of POST /upload: files staged into data/, not yet indexed."""

    files: list[FileResult]


class IndexRequest(BaseModel):
    """Optional body for POST /index. Omit (or send null filenames) to
    index every supported file currently in data/."""

    filenames: list[str] | None = None


class IndexResponse(BaseModel):
    """Outcome of POST /index plus the resulting database size."""

    files: list[FileResult]
    vector_count: int


class DocumentsResponse(BaseModel):
    """Distinct source filenames currently in the vector database."""

    documents: list[str]


# --- system ------------------------------------------------------------------


class StatusResponse(BaseModel):
    """Knowledge-base status plus the (read-only) pipeline settings —
    the same information the Streamlit sidebar displays today."""

    vector_count: int
    document_count: int
    documents: list[str]
    embedding_model: str
    llm_model: str
    chunk_size: int
    chunk_overlap: int
    top_k: int


class ClearDatabaseResponse(BaseModel):
    """Outcome of DELETE /database."""

    status: str  # "cleared"
    vector_count: int


class HealthResponse(BaseModel):
    """Liveness plus reachability of the two external dependencies."""

    status: str  # "ok" if everything reachable, else "degraded"
    chroma: bool
    ollama: bool
