# api/schemas/models.py
#
# Every request/response shape the API exposes, in one place. These
# mirror what the existing backend functions already return (e.g.
# ChatResponse matches rag.answer_question()'s dict exactly), so the
# service layer never has to reshape data -- it just passes it through.

from pydantic import BaseModel, Field, field_validator


# --- chat -------------------------------------------------------------------


class HistoryMessage(BaseModel):
    """A single turn in the conversation history sent with a chat request."""

    role: str = Field(description="'user' or 'assistant'")
    content: str = Field(description="The message text")


class ChatRequest(BaseModel):
    """A single question for the knowledge base, with optional context."""

    question: str = Field(
        ...,
        description="Natural-language question answered only from the indexed documents",
        json_schema_extra={"example": "How does Zephyra store knowledge?"},
    )

    # Bounded conversation history: at most 6 prior turns (3 user + 3 assistant).
    # The API layer enforces this so the LLM context window cannot grow unboundedly.
    history: list[HistoryMessage] = Field(
        default_factory=list,
        description=(
            "Recent conversation history (at most 6 messages). "
            "Role must be 'user' or 'assistant'. Sent to the LLM as prior context; "
            "does NOT affect document retrieval."
        ),
    )

    # When set, restricts vector retrieval to a single document's chunks.
    # None / absent means 'All Documents' (retrieve across everything).
    document_filter: str | None = Field(
        default=None,
        description=(
            "Restrict retrieval to this specific document filename. "
            "Omit or set null for All-Documents mode."
        ),
    )

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        """Strip and reject empty/whitespace-only questions (same rule
        the Streamlit UI enforces) -- FastAPI turns this into a 422."""
        v = v.strip()
        if not v:
            raise ValueError("question must not be empty")
        return v

    @field_validator("history")
    @classmethod
    def cap_history(cls, v: list[HistoryMessage]) -> list[HistoryMessage]:
        """Silently trim to the most recent 6 messages so callers that
        send an unbounded list don't overflow the LLM context window."""
        return v[-6:] if len(v) > 6 else v


class Source(BaseModel):
    """One retrieved chunk an answer was grounded on."""

    filename: str = Field(description="Source document the chunk came from")
    chunk_id: str = Field(description="Unique chunk id within the database")
    similarity: float = Field(
        description="Cosine similarity in [0, 1]; higher = more relevant"
    )
    preview: str | None = Field(
        default=None,
        description="Leading snippet of the chunk's text, for source previews",
    )
    # Citation metadata (populated when available)
    page: int | None = Field(
        default=None,
        description="1-based page number within the source document, if known",
    )
    slide: int | None = Field(
        default=None,
        description="1-based slide number within the presentation, if known",
    )
    sheet: str | None = Field(
        default=None,
        description="Worksheet name within the spreadsheet, if known",
    )
    section: str | None = Field(
        default=None,
        description="Document section heading the chunk belongs to, if known",
    )
    extraction_method: str | None = Field(
        default=None,
        description="Method used to extract text ('text' or 'ocr')",
    )
    document_id: str | None = Field(
        default=None,
        description="Unique document identifier",
    )


class ChatResponse(BaseModel):
    """Grounded answer plus the sources it came from."""

    answer: str = Field(description="Answer grounded in the indexed documents")
    sources: list[Source] = Field(
        description="Chunks the answer was based on, most relevant first"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "answer": "Zephyra stores knowledge in three tiers: ...",
                "sources": [
                    {
                        "filename": "zephyra.txt",
                        "chunk_id": "zephyra.txt-3",
                        "similarity": 0.85,
                        "page": None,
                    }
                ],
            }
        }
    }


# --- research ----------------------------------------------------------------


class ResearchRequest(BaseModel):
    """A research question to synthesize across ALL indexed documents."""

    question: str = Field(
        ...,
        description="Research question synthesized across all documents",
        json_schema_extra={"example": "What are the key themes across all documents?"},
    )

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question must not be empty")
        return v


class ResearchResponse(BaseModel):
    """Structured synthesis across multiple documents."""

    answer: str = Field(
        description="Structured synthesis in markdown (Executive Summary, "
        "Document Findings, Cross-Document Comparison, Differences, Gaps)"
    )
    sources: list[Source] = Field(
        description="All evidence chunks used, from multiple documents"
    )
    doc_count: int = Field(
        description="Number of distinct documents that contributed evidence",
        default=0,
    )


# --- documents / ingestion ---------------------------------------------------


class FileResult(BaseModel):
    """Per-file outcome for upload and index operations -- errors are
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


class DeleteDocumentResponse(BaseModel):
    """Outcome of DELETE /documents/{filename}."""

    filename: str
    status: str  # "deleted"
    vector_count: int


# --- collections -------------------------------------------------------------


class CollectionCreate(BaseModel):
    """Body for POST /collections."""

    name: str = Field(..., description="Collection display name")
    description: str = Field(default="", description="Optional description")
    color: str = Field(default="#3B82F6", description="Hex color code")
    icon: str = Field(default="folder", description="Lucide icon identifier")

    @field_validator("name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Collection name must not be empty")
        return v


class CollectionUpdate(BaseModel):
    """Body for PATCH /collections/{collection_id}."""

    name: str | None = None
    description: str | None = None
    color: str | None = None
    icon: str | None = None


class CollectionResponse(BaseModel):
    """Structured collection details."""

    id: str
    name: str
    description: str
    color: str
    icon: str
    created_at: str
    updated_at: str
    document_count: int = 0


class CollectionListResponse(BaseModel):
    """List of all user collections."""

    collections: list[CollectionResponse]


class DocumentMoveRequest(BaseModel):
    """Body for PATCH /documents/{filename} to assign/move collection."""

    collection_id: str | None = Field(
        default=None,
        description="Target collection ID, or null to set Uncategorized",
    )


class DocumentDetail(BaseModel):
    """Rich document metadata details."""

    document_id: str
    filename: str
    file_type: str
    file_size: int = 0
    chunk_count: int = 0
    extraction_method: str = "text"
    collection_id: str | None = None
    collection_name: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class DocumentListResponse(BaseModel):
    """Extended list of documents with metadata."""

    documents: list[DocumentDetail]


class TagAddRequest(BaseModel):
    """Body for POST /documents/{filename}/tags."""

    tag: str = Field(..., description="Tag name to add to the document")

    @field_validator("tag")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("Tag must not be empty")
        if len(v) > 50:
            raise ValueError("Tag must not exceed 50 characters")
        return v


class TagListResponse(BaseModel):
    """List of all system tags."""

    tags: list[str]


class TagActionResponse(BaseModel):
    """Outcome of adding or removing a tag from a document."""

    filename: str
    tags: list[str]


# --- system ------------------------------------------------------------------


class StatusResponse(BaseModel):
    """Knowledge-base status plus the (read-only) pipeline settings --
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

