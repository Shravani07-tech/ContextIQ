// TypeScript mirrors of the FastAPI Pydantic schemas
// (api/schemas/models.py). If a backend schema changes, this file
// changes with it — the API client and hooks import only from here.

export interface HealthResponse {
  status: "ok" | "degraded";
  chroma: boolean;
  ollama: boolean;
}

export interface DocumentsResponse {
  documents: string[];
}

export interface FileResult {
  filename: string;
  status: "saved" | "indexed" | "error";
  chunks_indexed?: number | null;
  error?: string | null;
}

export interface UploadResponse {
  files: FileResult[];
}

export interface IndexResponse {
  files: FileResult[];
  vector_count: number;
}

export interface Source {
  filename: string;
  chunk_id: string;
  similarity: number;
  /** Leading snippet of the chunk's text (for expandable previews). */
  preview?: string | null;
  /** 1-based page number within the source document, if known. */
  page?: number | null;
  /** Document section heading, if known. */
  section?: string | null;
  /** 1-based slide number (presentations), if known. */
  slide?: number | null;
  /** Worksheet name (spreadsheets), if known. */
  sheet?: string | null;
  /** Unique document identifier. */
  document_id?: string | null;
}

export interface VerificationItem {
  claim: string;
  status: "SUPPORTED" | "PARTIALLY_SUPPORTED" | "UNSUPPORTED" | "UNVERIFIABLE";
  citation_ids: string[];
  reason: string;
}

export interface ContradictionItem {
  topic: string;
  status: "CONTRADICTION" | "POTENTIAL_CONTRADICTION";
  claim_a: string;
  claim_b: string;
  source_a: string;
  source_b: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  reason: string;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
  suggested_questions?: string[];
  citation_verification?: VerificationItem[];
  contradictions?: ContradictionItem[];
  evidence_assessment?: EvidenceAssessment | null;
}

export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
}

/** Research Mode: synthesis across all documents */
export interface ResearchResponse {
  answer: string;
  sources: Source[];
  doc_count: number;
}


// --- chat UI state (not a backend schema — lives here because both
// hooks/useChat.tsx and multiple chat components need it) ------------------

export type ChatRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  /** Pre-formatted display time, e.g. "2:41 PM". */
  timestamp?: string;
  /** Chunks the answer was grounded on (assistant messages only). */
  sources?: Source[];
  /** Suggested follow-up questions (assistant messages only). */
  suggestedQuestions?: string[];
  /** Citation verification results evaluating support of claims. */
  citationVerification?: VerificationItem[];
  /** Contradictions detected between evidence sources. */
  contradictions?: ContradictionItem[];
  /** Rule-based evidence rating per verified claim. */
  evidenceAssessment?: EvidenceAssessment | null;
  /** The question this answer responds to (used for report export). */
  question?: string;
  /** Set on a failed system message so the UI can offer a "Retry"
      action that resends this exact question. */
  retryQuestion?: string;
}

export interface ClearDatabaseResponse {
  status: string;
  vector_count: number;
}

export interface DeleteDocumentResponse {
  filename: string;
  status: string;
  vector_count: number;
}

// --- client-side document metadata ------------------------------------------
// The backend only stores `filename` per chunk (see vector_store.py) —
// adding upload-time/size to its metadata would mean touching the
// ingestion write path, which Phase 5A explicitly keeps hands-off.
// Size, chunk count, and upload time are instead captured client-side
// at the moment of upload (all already available in the browser and
// in the existing /index response) and cached in localStorage. Files
// that entered the knowledge base before this cache existed — the
// demo corpus, anything ingested via the CLI — simply have no entry;
// the UI shows "—" for those rather than a fabricated value.
export interface DocumentMeta {
  sizeBytes: number;
  chunks: number;
  uploadedAt: number; // epoch ms
  /**
   * SHA-256 hash of the raw file bytes, computed in the browser at
   * upload time using the Web Crypto API. Used for content-based
   * duplicate detection: a re-uploaded file with a different name but
   * the same content will be caught by hash comparison, not filename.
   * Optional — documents uploaded before this field existed (via CLI
   * or before v1.1.0) simply have no hash entry.
   */
  hash?: string;
}

// --- chat sessions -----------------------------------------------------------
// Lightweight local conversation management. Sessions are stored in
// localStorage (key: contextiq.sessions.v1) and survive page refreshes.
// Nothing is sent to the server — all session state is client-only.
// Deleting a session never deletes documents; deleting a document never
// deletes unrelated sessions. References to deleted documents inside
// older messages remain intact (the filename is still shown).
export interface ChatSession {
  id: string;
  /** Auto-generated from the first user message (≤ 45 chars). */
  title: string;
  messages: ChatMessage[];
  createdAt: number; // epoch ms
  updatedAt: number; // epoch ms
}

export interface StatusResponse {
  vector_count: number;
  document_count: number;
  documents: string[];
  embedding_model: string;
  llm_model: string;
  chunk_size: number;
  chunk_overlap: number;
  top_k: number;
}

// --- Collections & Workspace Types -----------------------------------------

export interface Collection {
  id: string;
  name: string;
  description: string;
  color: string;
  icon: string;
  created_at: string;
  updated_at: string;
  document_count: number;
}

export interface CollectionCreate {
  name: string;
  description?: string;
  color?: string;
  icon?: string;
}

export interface CollectionUpdate {
  name?: string;
  description?: string;
  color?: string;
  icon?: string;
}

export interface CollectionListResponse {
  collections: Collection[];
}

export interface DocumentDetail {
  document_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  extraction_method: string;
  collection_id: string | null;
  collection_name: string | null;
  tags: string[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface DocumentListResponse {
  documents: DocumentDetail[];
}

export interface TagListResponse {
  tags: string[];
}

export interface TagActionResponse {
  filename: string;
  tags: string[];
}

export interface DocumentSummary {
  document_id: string;
  filename: string;
  status: "pending" | "generating" | "completed" | "failed";
  summary: string;
  key_points: string[];
  error?: string | null;
  generated_at?: string | null;
  version?: number;
}

export interface CompareRequest {
  filenames: string[];
  question?: string | null;
  collection_id?: string | null;
}

export interface CompareResponse {
  filenames: string[];
  question: string;
  summary: string;
  similarities: string[];
  differences: string[];
  document_a_only: string[];
  document_b_only: string[];
  sources: Source[];
  coverage?: DocumentCoverage[];
}



// --- Analysis features (api/schemas/insights.py) ----------------------------

/** Locator for a stored passage — always copied from the vector store. */
export interface SourceRef {
  filename: string;
  chunk_id: string;
  page?: number | null;
  slide?: number | null;
  sheet?: string | null;
  section?: string | null;
  document_id?: string | null;
  preview?: string | null;
  quote?: string | null;
}

export interface ScopeParams {
  collection_id?: string | null;
  filenames?: string[] | null;
}

export type DateCertainty =
  | "EXACT"
  | "APPROXIMATE"
  | "AMBIGUOUS"
  | "RELATIVE"
  | "UNKNOWN";

export interface TimelineDate {
  text: string;
  start: string | null;
  end: string | null;
  precision: string;
  certainty: DateCertainty;
  qualifier?: string | null;
  note?: string | null;
  in_source: boolean;
}

export interface TimelineEvent {
  id: string;
  date: TimelineDate;
  date_type: "EVENT" | "PUBLICATION" | "MODIFIED" | "OTHER";
  description: string;
  actors: string[];
  source: SourceRef;
}

export interface TimelineRequest extends ScopeParams {
  focus?: string | null;
  max_events?: number | null;
  use_llm?: boolean;
}

export interface TimelineResponse {
  scope: string;
  focus?: string | null;
  events: TimelineEvent[];
  undated_events: TimelineEvent[];
  document_dates: { filename: string; indexed_at?: string | null }[];
  extraction_method: "llm" | "pattern" | "none";
  chunks_analyzed: number;
  documents_analyzed: number;
  events_discarded: number;
  warnings: string[];
}

export type EvidenceRating =
  | "STRONG"
  | "MODERATE"
  | "LIMITED"
  | "CONTESTED"
  | "UNSUPPORTED"
  | "INSUFFICIENT";

export interface EvidencePassage extends SourceRef {
  relevance: "HIGH" | "MEDIUM" | "LOW" | "NONE";
  cited_by_check: boolean;
  source_group: string;
}

export interface ClaimAssessment {
  claim: string;
  rating: EvidenceRating;
  basis: "model-assisted" | "heuristic";
  factors: {
    relevance: string;
    directness: string;
    independent_sources: number;
    duplicates_collapsed: number;
    contradiction: "NONE" | "POTENTIAL" | "CONFLICT";
  };
  explanation: string[];
  passages: EvidencePassage[];
  contradictions: {
    topic?: string | null;
    status?: string | null;
    severity?: string | null;
    source_a?: string | null;
    source_b?: string | null;
  }[];
}

export interface EvidenceAssessment {
  claims: ClaimAssessment[];
  counts: Record<EvidenceRating, number>;
  overall: string;
  documents_considered: number;
  independent_sources: number;
  disclaimer: string;
}

export interface EvidenceAssessRequest extends ScopeParams {
  claim: string;
  check_contradictions?: boolean;
}

export interface EvidenceAssessResponse {
  claim: string;
  scope: string;
  assessment: ClaimAssessment;
  disclaimer: string;
  model_checked: boolean;
  warnings: string[];
}

export interface DocumentCoverage {
  filename: string;
  passages: number;
  best_similarity?: number | null;
  note?: string | null;
}

// --- Knowledge graph (C10) ---------------------------------------------------

export interface GraphExtraction {
  filename: string;
  status: "completed" | "failed";
  method?: "llm" | "pattern" | "none" | null;
  error?: string | null;
  chunks_analyzed: number;
  entity_count: number;
  relation_count: number;
  extracted_at?: string | null;
}

export interface GraphBuildResponse {
  scope: string;
  processed: GraphExtraction[];
  remaining: number;
}

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  mentions: number;
  documents: number;
  degree: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
  status: "SUPPORTED" | "UNCERTAIN";
  evidence_count: number;
}

export interface GraphResponse {
  scope: string;
  documents_in_scope: number;
  documents_extracted: number;
  extractions: GraphExtraction[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  truncated: boolean;
  total_entities: number;
  possible_duplicates: { a: string; b: string; a_name: string; b_name: string; reason: string }[];
}

export interface EntityRef {
  id: string;
  name: string;
  type: string;
}

export interface EntityDetail {
  entity: EntityRef;
  mentions: { surface: string; source: SourceRef }[];
  relations: {
    id: string;
    relation: string;
    status: "SUPPORTED" | "UNCERTAIN";
    direction: "outgoing" | "incoming";
    other: EntityRef;
    evidence?: string | null;
    source: SourceRef;
  }[];
  documents: string[];
}
