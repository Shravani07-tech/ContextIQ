// Strongly typed API client for the ContextIQ FastAPI backend.
// Centralizes every request: base URL from the environment, JSON
// handling, and error normalization. Components never call fetch —
// they use the TanStack Query hooks in hooks/, which call this.

import type {
  ChatResponse,
  ClearDatabaseResponse,
  DeleteDocumentResponse,
  DocumentsResponse,
  HealthResponse,
  HistoryMessage,
  IndexResponse,
  Source,
  StatusResponse,
  UploadResponse,
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
  documents: () => request<DocumentsResponse>("/documents"),

  /** GET /status — knowledge-base counts + pipeline settings. */
  status: () => request<StatusResponse>("/status"),

  /**
   * POST /upload — stage PDF/TXT files into the backend's data folder.
   *
   * Uses XMLHttpRequest instead of fetch because fetch cannot report
   * UPLOAD progress; XHR's upload.onprogress gives the byte-level
   * percentage the dropzone's progress bar displays. Returns both the
   * promise AND a cancel() handle (XHR supports .abort() natively),
   * so the UI can offer a real Cancel button instead of just waiting
   * it out.
   */
  upload: (
    files: File[],
    onProgress?: (percent: number) => void,
  ): { promise: Promise<UploadResponse>; cancel: () => void } => {
    const xhr = new XMLHttpRequest();
    const promise = new Promise<UploadResponse>((resolve, reject) => {
      xhr.open("POST", `${API_URL}/upload`);

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

  /** POST /chat -- grounded answer + sources for one question.
      180s timeout: double the worst normal CPU-generation time. */
  chat: (
    question: string,
    opts?: { history?: HistoryMessage[]; documentFilter?: string | null },
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
        }),
      },
      180_000,
    ),

  /**
   * POST /chat/stream — same grounded pipeline as chat(), but the
   * answer arrives progressively over Server-Sent Events instead of
   * as one JSON blob.
   *
   * Takes callbacks rather than returning a promise-of-the-answer,
   * since the whole point is delivering partial results as they
   * arrive. `signal` is the caller's own AbortController — when it
   * fires, this function stops silently (no callback), because the
   * caller already knows it stopped deliberately (it's the one that
   * called .abort()) and owns finalizing the UI state from whatever
   * was accumulated so far.
   */
  chatStream: async (
    question: string,
    callbacks: {
      onSources: (sources: Source[]) => void;
      onToken: (text: string) => void;
      onDone: () => void;
      onError: (detail: string) => void;
    },
    signal: AbortSignal,
    opts?: {
      history?: HistoryMessage[];
      documentFilter?: string | null;
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

        // SSE frames are separated by a blank line.
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
          else if (event.type === "done") {
            callbacks.onDone();
            return;
          } else if (event.type === "error") {
            callbacks.onError(event.detail);
            return;
          }
        }
      }
      // Stream closed without an explicit "done" event — treat as
      // complete rather than leaving the caller waiting forever.
      callbacks.onDone();
    } catch {
      if (signal.aborted) return;
      callbacks.onError("The connection was interrupted mid-answer.");
    }
  },

  /** DELETE /database — clear every vector (files on disk are kept). */
  clearDatabase: () =>
    request<ClearDatabaseResponse>("/database", { method: "DELETE" }),

  /** DELETE /documents/{filename} — remove one document; every other
      document in the knowledge base is untouched. */
  deleteDocument: (filename: string) =>
    request<DeleteDocumentResponse>(
      `/documents/${encodeURIComponent(filename)}`,
      { method: "DELETE" },
    ),
};
