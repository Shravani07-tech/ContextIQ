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
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
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
