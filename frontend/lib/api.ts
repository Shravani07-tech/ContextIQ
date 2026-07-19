// Strongly typed API client for the ContextIQ FastAPI backend.
// Centralizes every request: base URL from the environment, JSON
// handling, and error normalization. Components never call fetch —
// they use the TanStack Query hooks in hooks/, which call this.

import type {
  ChatResponse,
  ClearDatabaseResponse,
  DocumentsResponse,
  HealthResponse,
  IndexResponse,
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
    // FastAPI errors carry {"detail": "..."} — surface it when present.
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // Non-JSON error body — keep the generic message.
    }
    throw new ApiError(response.status, detail);
  }

  return response.json() as Promise<T>;
}

export const api = {
  /** GET /health — liveness + Chroma/Ollama reachability. */
  health: () => request<HealthResponse>("/health"),

  /** GET /documents — filenames currently in the vector database. */
  documents: () => request<DocumentsResponse>("/documents"),

  /**
   * POST /upload — stage PDF/TXT files into the backend's data folder.
   *
   * Uses XMLHttpRequest instead of fetch because fetch cannot report
   * UPLOAD progress; XHR's upload.onprogress gives the byte-level
   * percentage the dropzone's progress bar displays.
   */
  upload: (files: File[], onProgress?: (percent: number) => void) =>
    new Promise<UploadResponse>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
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
          let detail = `Request failed (${xhr.status})`;
          try {
            const body = JSON.parse(xhr.responseText);
            if (typeof body?.detail === "string") detail = body.detail;
          } catch {
            // Non-JSON error body — keep the generic message.
          }
          reject(new ApiError(xhr.status, detail));
        }
      };
      xhr.onerror = () =>
        reject(new ApiError(0, "Backend is unreachable. Is the API running?"));

      const form = new FormData();
      for (const file of files) form.append("files", file);
      xhr.send(form);
    }),

  /** POST /index — run the ingestion pipeline over staged files. */
  index: (filenames?: string[]) =>
    request<IndexResponse>("/index", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filenames: filenames ?? null }),
    }),

  /** POST /chat — grounded answer + sources for one question.
      180s timeout: double the worst normal CPU-generation time. */
  chat: (question: string) =>
    request<ChatResponse>(
      "/chat",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      },
      180_000,
    ),

  /** DELETE /database — clear every vector (files on disk are kept). */
  clearDatabase: () =>
    request<ClearDatabaseResponse>("/database", { method: "DELETE" }),
};
