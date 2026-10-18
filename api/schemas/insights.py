# api/schemas/insights.py
#
# Request/response contracts for the ContextIQ 2.0 analysis features:
# timeline extraction (C7), evidence assessment (C8), the knowledge
# graph (C10) and bounded agentic research (C11). Kept apart from
# models.py so the original chat/ingestion contract stays readable.
#
# Every request that names documents is bounded here (list lengths,
# string lengths) before any service runs; scope membership itself is
# validated by scope.resolve_scope().

from pydantic import BaseModel, Field, field_validator


def _strip_optional(v: str | None, max_len: int) -> str | None:
    if v is None:
        return None
    v = v.strip()
    if len(v) > max_len:
        raise ValueError(f"must be at most {max_len} characters")
    return v or None


class ScopedRequest(BaseModel):
    collection_id: str | None = Field(
        default=None, description="Restrict to documents in this collection"
    )
    filenames: list[str] | None = Field(
        default=None,
        max_length=25,
        description="Restrict to these documents (must be inside the collection, if one is given)",
    )


class SourceRef(BaseModel):
    """Locator for a stored passage. Always copied from the vector store."""

    filename: str
    chunk_id: str
    page: int | None = None
    slide: int | None = None
    sheet: str | None = None
    section: str | None = None
    document_id: str | None = None
    preview: str | None = None
    quote: str | None = None


# --- C7 timeline ---------------------------------------------------------------


class TimelineRequest(ScopedRequest):
    focus: str | None = Field(
        default=None,
        description="Optional topic to focus on (uses retrieval instead of a full scan)",
    )
    max_events: int | None = Field(default=None, ge=1, le=100)
    use_llm: bool = Field(
        default=True,
        description="False forces the deterministic pattern-based extractor",
    )

    @field_validator("focus")
    @classmethod
    def _focus(cls, v: str | None) -> str | None:
        return _strip_optional(v, 300)


class TimelineDate(BaseModel):
    text: str = Field(description="Date wording exactly as written in the source")
    start: str | None = Field(description="Partial ISO start (e.g. '2024', '2024-03')")
    end: str | None = None
    precision: str = Field(description="day|month|quarter|half|year|decade|range|unknown")
    certainty: str = Field(description="EXACT|APPROXIMATE|AMBIGUOUS|RELATIVE|UNKNOWN")
    qualifier: str | None = Field(default=None, description="before/after/by/since, if stated")
    note: str | None = None
    in_source: bool = Field(description="True when the wording was found in the cited passage")


class TimelineEvent(BaseModel):
    id: str
    date: TimelineDate
    date_type: str = Field(description="EVENT|PUBLICATION|MODIFIED|OTHER")
    description: str
    actors: list[str] = Field(default_factory=list)
    source: SourceRef


class DocumentDate(BaseModel):
    filename: str
    indexed_at: str | None = Field(
        default=None, description="When the file was indexed into ContextIQ (not an event date)"
    )


class TimelineResponse(BaseModel):
    scope: str
    focus: str | None = None
    events: list[TimelineEvent]
    undated_events: list[TimelineEvent] = Field(
        default_factory=list,
        description="Events whose date is missing, relative, or not found in the source",
    )
    document_dates: list[DocumentDate] = Field(default_factory=list)
    extraction_method: str = Field(description="llm | pattern | none")
    chunks_analyzed: int
    documents_analyzed: int
    events_discarded: int = 0
    warnings: list[str] = Field(default_factory=list)


# --- C8 evidence assessment ----------------------------------------------------


class EvidencePassage(SourceRef):
    relevance: str = Field(description="HIGH|MEDIUM|LOW|NONE keyword overlap with the claim")
    cited_by_check: bool = Field(description="True when the citation check cited this passage")
    source_group: str = Field(description="Independent-source group (near-duplicates share one)")


class EvidenceFactors(BaseModel):
    relevance: str
    directness: str = Field(description="DIRECT|PARTIAL|NONE|UNKNOWN|NOT_ASSESSED")
    independent_sources: int
    duplicates_collapsed: int = 0
    contradiction: str = Field(description="NONE|POTENTIAL|CONFLICT")


class RelatedContradiction(BaseModel):
    topic: str | None = None
    status: str | None = None
    severity: str | None = None
    source_a: str | None = None
    source_b: str | None = None


class ClaimAssessment(BaseModel):
    claim: str
    rating: str = Field(description="STRONG|MODERATE|LIMITED|CONTESTED|UNSUPPORTED|INSUFFICIENT")
    basis: str = Field(description="model-assisted | heuristic")
    factors: EvidenceFactors
    explanation: list[str]
    passages: list[EvidencePassage] = Field(default_factory=list)
    contradictions: list[RelatedContradiction] = Field(default_factory=list)


class EvidenceAssessment(BaseModel):
    claims: list[ClaimAssessment]
    counts: dict[str, int]
    overall: str
    documents_considered: int
    independent_sources: int
    disclaimer: str


class EvidenceAssessRequest(ScopedRequest):
    claim: str = Field(..., description="The statement to check against your documents")
    check_contradictions: bool = True

    @field_validator("claim")
    @classmethod
    def _claim(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("claim must not be empty")
        if len(v) > 1000:
            raise ValueError("claim must be at most 1000 characters")
        return v


class EvidenceAssessResponse(BaseModel):
    claim: str
    scope: str
    assessment: ClaimAssessment
    disclaimer: str
    model_checked: bool = Field(description="False when the local model was unavailable")
    warnings: list[str] = Field(default_factory=list)


class DocumentCoverage(BaseModel):
    filename: str
    passages: int
    best_similarity: float | None = None
    note: str | None = None


# --- C10 knowledge graph -------------------------------------------------------


class GraphBuildRequest(ScopedRequest):
    force: bool = Field(default=False, description="Re-extract documents already processed")
    use_llm: bool = Field(default=True, description="False forces the pattern-based extractor")


class GraphExtraction(BaseModel):
    filename: str
    status: str = Field(description="completed | failed")
    method: str | None = Field(default=None, description="llm | pattern | none")
    error: str | None = None
    chunks_analyzed: int = 0
    entity_count: int = 0
    relation_count: int = 0
    extracted_at: str | None = None


class GraphBuildResponse(BaseModel):
    scope: str
    processed: list[GraphExtraction]
    remaining: int = Field(description="Documents in scope still waiting for extraction")


class GraphNode(BaseModel):
    id: str
    name: str
    type: str
    mentions: int
    documents: int
    degree: int


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: str
    status: str = Field(description="SUPPORTED (quote found in passage) | UNCERTAIN")
    evidence_count: int


class PossibleDuplicate(BaseModel):
    a: str
    b: str
    a_name: str
    b_name: str
    reason: str


class GraphResponse(BaseModel):
    scope: str
    documents_in_scope: int
    documents_extracted: int
    extractions: list[GraphExtraction]
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    truncated: bool
    total_entities: int
    possible_duplicates: list[PossibleDuplicate] = Field(default_factory=list)


class EntityRef(BaseModel):
    id: str
    name: str
    type: str


class EntityMention(BaseModel):
    surface: str
    source: SourceRef


class EntityRelation(BaseModel):
    id: str
    relation: str
    status: str
    direction: str
    other: EntityRef
    evidence: str | None = None
    source: SourceRef


class EntityDetailResponse(BaseModel):
    entity: EntityRef
    mentions: list[EntityMention]
    relations: list[EntityRelation]
    documents: list[str]


# --- C11 bounded agentic research ----------------------------------------------


class AgentResearchRequest(ScopedRequest):
    question: str = Field(..., description="The research question")
    max_subquestions: int | None = Field(
        default=None, ge=1, le=6, description="Lower the sub-question ceiling for this run"
    )

    @field_validator("question")
    @classmethod
    def _question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question must not be empty")
        if len(v) > 2000:
            raise ValueError("question must be at most 2000 characters")
        return v


class ResearchSubquestion(BaseModel):
    question: str
    status: str = Field(description="ANSWERED | PARTIAL | UNRESOLVED")
    queries: list[str] = Field(default_factory=list, description="Searches actually run")
    source_labels: list[str] = Field(default_factory=list, description="Evidence labels (S1, S2, ...)")
    note: str | None = None


class ResearchSource(BaseModel):
    label: str
    filename: str
    chunk_id: str
    similarity: float
    page: int | None = None
    slide: int | None = None
    sheet: str | None = None
    section: str | None = None
    document_id: str | None = None
    preview: str | None = None


class ResearchStep(BaseModel):
    stage: str
    message: str
    found: int | None = None


class AgentResearchResult(BaseModel):
    question: str
    status: str = Field(description="COMPLETED | PARTIAL | CANCELLED | FAILED")
    scope: str
    answer: str
    plan_method: str = Field(description="single | llm | heuristic")
    subquestions: list[ResearchSubquestion]
    unresolved: list[str]
    sources: list[ResearchSource]
    citation_verification: list[dict] = Field(default_factory=list)
    contradictions: list[dict] = Field(default_factory=list)
    evidence_assessment: EvidenceAssessment | None = None
    steps: list[ResearchStep]
    warnings: list[str] = Field(default_factory=list)
    limits: dict
