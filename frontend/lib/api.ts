// Strongly typed API client for the ContextIQ FastAPI backend.
// Centralizes every request: base URL from the environment, JSON
// handling, and error normalization. Components never call fetch —
// they use the TanStack Query hooks in hooks/, which call this.

import type {
  ChatResponse,
  ClearDatabaseResponse,
  Collection,
  CollectionCreate,
  CollectionListResponse,
  CollectionUpdate,
  CompareRequest,
  CompareResponse,
  DeleteDocumentResponse,
  DocumentDetail,
  DocumentListResponse,
  DocumentSummary,
  DocumentsResponse,
  HealthResponse,
  HistoryMessage,
  IndexResponse,
  Source,
  StatusResponse,
  TagActionResponse,
  TagListResponse,
  UploadResponse,
  VerificationItem,
} from "@/lib/types";



const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Normalized API failure: status 0 means the backend is unreachable. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Best-effort human-readable message for a non-OK response. FastAPI
 * errors carry {"detail": "..."} — surface that when present, else
 * fall back to a generic "Request failed (status)". Accepts the raw
 * body text (works for both fetch responses and XHR responseText).
 */
function errorDetail(rawBody: string, status: number): string {
  try {
    const body = JSON.parse(rawBody);
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    // Non-JSON error body — keep the generic message.
  }
  return `Request failed (${status})`;
}

async function request<T>(
  path: string,
  init?: RequestInit,
  timeoutMs?: number,
): Promise<T> {
  // Optional timeout: without one, a hung request would spin forever
  // (fetch has no default timeout). Used by /chat, where local LLM
  // generation is slow-but-bounded — 30-90s is normal, minutes is not.
  const controller = timeoutMs ? new AbortController() : undefined;
  const timer = controller
    ? setTimeout(() => controller.abort(), timeoutMs)
    : undefined;

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: controller?.signal,
    });
  } catch {
    if (controller?.signal.aborted) {
      throw new ApiError(
        408,
        "The answer timed out — the model may be busy. Try asking again.",
      );
    }
    // Network-level failure — server down, wrong URL, CORS.
    throw new ApiError(0, "Backend is unreachable. Is the API running?");
  } finally {
    if (timer) clearTimeout(timer);
  }

  if (!response.ok) {
    throw new ApiError(
      response.status,
      errorDetail(await response.text(), response.status),
    );
  }

  return response.json() as Promise<T>;
}

export const api = {
  /** GET /health — liveness + Chroma/Ollama reachability. */
  health: () => request<HealthResponse>("/health"),

  /** GET /documents — filenames currently in the vector database. */
  documents: (params?: { collection_id?: string; tag?: string }) => {
    const query = new URLSearchParams();
    if (params?.collection_id) query.set("collection_id", params.collection_id);
    if (params?.tag) query.set("tag", params.tag);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request<DocumentsResponse>(`/documents${qs}`);
  },

  /** GET /documents?detail=true — rich document metadata details. */
  detailedDocuments: (params?: { collection_id?: string; tag?: string }) => {
    const query = new URLSearchParams({ detail: "true" });
    if (params?.collection_id) query.set("collection_id", params.collection_id);
    if (params?.tag) query.set("tag", params.tag);
    return request<DocumentListResponse>(`/documents?${query.toString()}`);
  },

  /** GET /documents/{filename} — metadata detail for one document. */
  documentDetail: (filename: string) =>
    request<DocumentDetail>(`/documents/${encodeURIComponent(filename)}`),

  /** GET /documents/{filename}/summary — fetch document summary. */
  documentSummary: (filename: string) =>
    request<DocumentSummary>(`/documents/${encodeURIComponent(filename)}/summary`),

  /** POST /documents/{filename}/summary/retry — retry or force summary generation. */
  retryDocumentSummary: (filename: string) =>
    request<DocumentSummary>(`/documents/${encodeURIComponent(filename)}/summary/retry`, {
      method: "POST",
    }),

  /** POST /compare — compare selected documents. */
  compare: (data: CompareRequest) =>
    request<CompareResponse>(
      "/compare",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      },
      120_000,
    ),


  /** PATCH /documents/{filename} — assign or move document to a collection. */
  moveDocument: (filename: string, collectionId: string | null) =>
    request<DocumentDetail>(`/documents/${encodeURIComponent(filename)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ collection_id: collectionId }),
    }),

  /** POST /documents/{filename}/tags — add a tag to a document. */
  addTag: (filename: string, tag: string) =>
    request<TagActionResponse>(`/documents/${encodeURIComponent(filename)}/tags`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tag }),
    }),

  /** DELETE /documents/{filename}/tags/{tag} — remove a tag from a document. */
  removeTag: (filename: string, tag: string) =>
    request<TagActionResponse>(
      `/documents/${encodeURIComponent(filename)}/tags/${encodeURIComponent(tag)}`,
      { method: "DELETE" },
    ),

  /** GET /tags — list all unique system tags. */
  tags: () => request<TagListResponse>("/tags"),

  /** GET /collections — list all collections. */
  collections: () => request<CollectionListResponse>("/collections"),

  /** POST /collections — create a new collection. */
  createCollection: (data: CollectionCreate) =>
    request<Collection>("/collections", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  /** PATCH /collections/{id} — update collection metadata. */
  updateCollection: (id: string, data: CollectionUpdate) =>
    request<Collection>(`/collections/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  /** DELETE /collections/{id} — delete collection safely (documents revert to Uncategorized). */
  deleteCollection: (id: string) =>
    request<{ status: string; collection_id: string }>(`/collections/${id}`, {
      method: "DELETE",
    }),

  /** GET /status — knowledge-base counts + pipeline settings. */
  status: () => request<StatusResponse>("/status"),

  /**
   * POST /upload — stage PDF/TXT files into the backend's data folder.
   * Optionally assigns uploaded files directly to a target collection_id.
   */
  upload: (
    files: File[],
    onProgress?: (percent: number) => void,
    collectionId?: string | null,
  ): { promise: Promise<UploadResponse>; cancel: () => void } => {
    const xhr = new XMLHttpRequest();
    const promise = new Promise<UploadResponse>((resolve, reject) => {
      const url = collectionId
        ? `${API_URL}/upload?collection_id=${encodeURIComponent(collectionId)}`
        : `${API_URL}/upload`;
      xhr.open("POST", url);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText) as UploadResponse);
        } else {
          reject(
            new ApiError(xhr.status, errorDetail(xhr.responseText, xhr.status)),
          );
        }
      };
      xhr.onerror = () =>
        reject(new ApiError(0, "Backend is unreachable. Is the API running?"));
      xhr.onabort = () => reject(new ApiError(0, "Upload cancelled."));

      const form = new FormData();
      for (const file of files) form.append("files", file);
      xhr.send(form);
    });

    return { promise, cancel: () => xhr.abort() };
  },

  /** POST /index — run the ingestion pipeline over staged files. */
  index: (filenames?: string[]) =>
    request<IndexResponse>("/index", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filenames: filenames ?? null }),
    }),

  /** POST /chat -- grounded answer + sources for one question. */
  chat: (
    question: string,
    opts?: {
      history?: HistoryMessage[];
      documentFilter?: string | null;
      collectionId?: string | null;
      tag?: string | null;
      tags?: string[] | null;
    },
  ) =>
    request<ChatResponse>(
      "/chat",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          history: opts?.history ?? [],
          document_filter: opts?.documentFilter ?? null,
          collection_id: opts?.collectionId ?? null,
          tag: opts?.tag ?? null,
          tags: opts?.tags ?? null,
        }),
      },
      180_000,
    ),

  /**
   * POST /chat/stream — same grounded pipeline as chat(), but the
   * answer arrives progressively over Server-Sent Events.
   */
  chatStream: async (
    question: string,
    callbacks: {
      onSources: (sources: Source[]) => void;
      onToken: (text: string) => void;
      onSuggestedQuestions?: (questions: string[]) => void;
      onCitationVerification?: (verifications: VerificationItem[]) => void;
      onDone: () => void;
      onError: (detail: string) => void;
    },
    signal: AbortSignal,
    opts?: {
      history?: HistoryMessage[];
      documentFilter?: string | null;
      collectionId?: string | null;
      tag?: string | null;
      tags?: string[] | null;
    },
  ): Promise<void> => {
    let response: Response;
    try {
      response = await fetch(`${API_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          history: opts?.history ?? [],
          document_filter: opts?.documentFilter ?? null,
          collection_id: opts?.collectionId ?? null,
          tag: opts?.tag ?? null,
          tags: opts?.tags ?? null,
        }),
        signal,
      });
    } catch {
      if (signal.aborted) return;
      callbacks.onError("Backend is unreachable. Is the API running?");
      return;
    }

    if (!response.ok || !response.body) {
      callbacks.onError(errorDetail(await response.text(), response.status));
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let sepIndex: number;
        while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
          const frame = buffer.slice(0, sepIndex);
          buffer = buffer.slice(sepIndex + 2);
          const dataLine = frame
            .split("\n")
            .find((line) => line.startsWith("data: "));
          if (!dataLine) continue;

          const event = JSON.parse(dataLine.slice("data: ".length));
          if (event.type === "sources") callbacks.onSources(event.sources);
          else if (event.type === "token") callbacks.onToken(event.text);
          else if (event.type === "suggested_questions") {
            callbacks.onSuggestedQuestions?.(event.questions);
          } else if (event.type === "citation_verification") {
            callbacks.onCitationVerification?.(event.verifications);
          } else if (event.type === "done") {
            callbacks.onDone();
            return;
          } else if (event.type === "error") {
            callbacks.onError(event.detail);
            return;
          }
        }
      }
      callbacks.onDone();
    } catch {
      if (signal.aborted) return;
      callbacks.onError("The connection was interrupted mid-answer.");
    }
  },

  /** DELETE /database — clear every vector (files on disk are kept). */
  clearDatabase: () =>
    request<ClearDatabaseResponse>("/database", { method: "DELETE" }),

  /** DELETE /documents/{filename} — remove one document. */
  deleteDocument: (filename: string) =>
    request<DeleteDocumentResponse>(
      `/documents/${encodeURIComponent(filename)}`,
      { method: "DELETE" },
    ),

  /**
   * POST /research/stream — research synthesis across scoped or all documents.
   */
  researchStream: async (
    question: string,
    callbacks: {
      onSources: (sources: Source[], docCount: number) => void;
      onToken: (text: string) => void;
      onDone: () => void;
      onError: (detail: string) => void;
    },
    signal: AbortSignal,
    opts?: {
      collectionId?: string | null;
      tag?: string | null;
      tags?: string[] | null;
    },
  ): Promise<void> => {
    let response: Response;
    try {
      response = await fetch(`${API_URL}/research/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          collection_id: opts?.collectionId ?? null,
          tag: opts?.tag ?? null,
          tags: opts?.tags ?? null,
        }),
        signal,
      });
    } catch {
      if (signal.aborted) return;
      callbacks.onError("Backend is unreachable. Is the API running?");
      return;
    }

    if (!response.ok || !response.body) {
      callbacks.onError(errorDetail(await response.text(), response.status));
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let sepIndex: number;
        while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
          const frame = buffer.slice(0, sepIndex);
          buffer = buffer.slice(sepIndex + 2);
          const dataLine = frame
            .split("\n")
            .find((line) => line.startsWith("data: "));
          if (!dataLine) continue;

          const event = JSON.parse(dataLine.slice("data: ".length));
          if (event.type === "sources")
            callbacks.onSources(event.sources, event.doc_count ?? 0);
          else if (event.type === "token") callbacks.onToken(event.text);
          else if (event.type === "done") {
            callbacks.onDone();
            return;
          } else if (event.type === "error") {
            callbacks.onError(event.detail);
            return;
          }
        }
      }
      callbacks.onDone();
    } catch {
      if (signal.aborted) return;
      callbacks.onError("The connection was interrupted mid-answer.");
    }
  },
};
