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

export interface ClearDatabaseResponse {
  status: string;
  vector_count: number;
}
