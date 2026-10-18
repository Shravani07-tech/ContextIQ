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
  EvidenceAssessment,
  EvidenceAssessRequest,
  EvidenceAssessResponse,
  EntityDetail,
  GraphBuildResponse,
  GraphResponse,
  HealthResponse,
  HistoryMessage,
  IndexResponse,
  Source,
  StatusResponse,
  TagActionResponse,
  ScopeParams,
  TagListResponse,
  AgentResearchResult,
  ResearchStep,
  ResearchSubquestion,
  TimelineEvent,
  TimelineRequest,
  TimelineResponse,
  UploadResponse,
  VerificationItem,
  ContradictionItem,
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

/** Query string for scoped GET endpoints (collection + repeated filenames). */
function scopeQuery(params: ScopeParams & { limit?: number }): string {
  const q = new URLSearchParams();
  if (params.collection_id) q.set("collection_id", params.collection_id);
  for (const f of params.filenames ?? []) q.append("filenames", f);
  if (params.limit) q.set("limit", String(params.limit));
  return q.toString();
}

/** A decoded SSE frame. Payload fields depend on `type`; each endpoint's
    dispatcher reads only the fields its event types define. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type SSEEvent = { type: string; [key: string]: any };

/**
 * POST a JSON body to an SSE endpoint and dispatch each `data:` frame.
 * Shared by every streaming endpoint so frame buffering (frames split
 * across network chunks), the terminal done/error events, and abort
 * handling behave identically everywhere. `onEvent` handles every other
 * event type.
 */
async function streamSSE(
  path: string,
  body: unknown,
  signal: AbortSignal,
  handlers: {
    onEvent: (event: SSEEvent) => void;
    onDone: () => void;
    onError: (detail: string) => void;
  },
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch {
    if (signal.aborted) return;
    handlers.onError("Backend is unreachable. Is the API running?");
    return;
  }

  if (!response.ok || !response.body) {
    handlers.onError(errorDetail(await response.text(), response.status));
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
        if (event.type === "done") {
          handlers.onDone();
          return;
        }
        if (event.type === "error") {
          handlers.onError(event.detail);
          return;
        }
        handlers.onEvent(event);
      }
    }
    handlers.onDone();
  } catch {
    if (signal.aborted) return;
    handlers.onError("The connection was interrupted mid-answer.");
  }
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


  /** POST /evidence/assess — rate how well the documents support a statement. */
  assessEvidence: (data: EvidenceAssessRequest) =>
    request<EvidenceAssessResponse>(
      "/evidence/assess",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      },
      150_000,
    ),

  /** POST /graph/build — extract the knowledge graph for documents in scope. */
  buildGraph: (data: ScopeParams & { force?: boolean }) =>
    request<GraphBuildResponse>(
      "/graph/build",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      },
      600_000,
    ),

  /** GET /graph — nodes and edges for a scope. */
  graph: (params: ScopeParams & { limit?: number }) =>
    request<GraphResponse>(`/graph?${scopeQuery(params)}`),

  /** GET /graph/entities/{id} — one entity with mentions and evidence. */
  graphEntity: (id: string, params: ScopeParams) =>
    request<EntityDetail>(`/graph/entities/${encodeURIComponent(id)}?${scopeQuery(params)}`),

  /** POST /timeline — source-linked timeline for a collection or selection. */
  timeline: (data: TimelineRequest) =>
    request<TimelineResponse>(
      "/timeline",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      },
      180_000,
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
      onContradictions?: (contradictions: ContradictionItem[]) => void;
      onEvidenceAssessment?: (assessment: EvidenceAssessment) => void;
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
  ): Promise<void> =>
    streamSSE(
      "/chat/stream",
      {
        question,
        history: opts?.history ?? [],
        document_filter: opts?.documentFilter ?? null,
        collection_id: opts?.collectionId ?? null,
        tag: opts?.tag ?? null,
        tags: opts?.tags ?? null,
      },
      signal,
      {
        onDone: callbacks.onDone,
        onError: callbacks.onError,
        onEvent: (event) => {
          const e = event;
          if (e.type === "sources") callbacks.onSources(e.sources);
          else if (e.type === "token") callbacks.onToken(e.text);
          else if (e.type === "suggested_questions") callbacks.onSuggestedQuestions?.(e.questions);
          else if (e.type === "citation_verification") callbacks.onCitationVerification?.(e.verifications);
          else if (e.type === "contradictions") callbacks.onContradictions?.(e.contradictions);
          else if (e.type === "evidence_assessment") callbacks.onEvidenceAssessment?.(e.assessment);
        },
      },
    ),

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
  ): Promise<void> =>
    streamSSE(
      "/research/stream",
      {
        question,
        collection_id: opts?.collectionId ?? null,
        tag: opts?.tag ?? null,
        tags: opts?.tags ?? null,
      },
      signal,
      {
        onDone: callbacks.onDone,
        onError: callbacks.onError,
        onEvent: (event) => {
          const e = event;
          if (e.type === "sources") callbacks.onSources(e.sources, e.doc_count ?? 0);
          else if (e.type === "token") callbacks.onToken(e.text);
        },
      },
    ),

  /**
   * POST /research/agent/stream — bounded multi-step research (C11):
   * progress steps, the plan, sources, the streamed answer, and finally
   * one structured result.
   */
  agentResearchStream: (
    question: string,
    callbacks: {
      onProgress?: (step: ResearchStep) => void;
      onPlan?: (subquestions: string[]) => void;
      onSources?: (sources: Source[]) => void;
      onToken: (text: string) => void;
      onResult: (result: AgentResearchResult) => void;
      onDone: () => void;
      onError: (detail: string) => void;
    },
    signal: AbortSignal,
    scope?: ScopeParams,
  ): Promise<void> =>
    streamSSE(
      "/research/agent/stream",
      {
        question,
        collection_id: scope?.collection_id ?? null,
        filenames: scope?.filenames ?? null,
      },
      signal,
      {
        onDone: callbacks.onDone,
        onError: callbacks.onError,
        onEvent: (event) => {
          const e = event;
          if (e.type === "progress") callbacks.onProgress?.(e as unknown as ResearchStep);
          else if (e.type === "plan") callbacks.onPlan?.(e.subquestions);
          else if (e.type === "sources") callbacks.onSources?.(e.sources);
          else if (e.type === "token") callbacks.onToken(e.text);
          else if (e.type === "result") callbacks.onResult(e.result);
        },
      },
    ),

  /** POST /research/export — download a Markdown, PDF, or Plain Text report. */
  exportResearchReport: async (payload: {
    format: "markdown" | "pdf" | "txt";
    question: string;
    answer: string;
    sources: Source[];
    doc_count?: number;
    citation_verification?: VerificationItem[];
    contradictions?: ContradictionItem[];
    collection_name?: string | null;
    document_filter?: string | null;
    timeline?: TimelineEvent[];
    evidence_assessment?: EvidenceAssessment | null;
    subquestions?: ResearchSubquestion[];
    unresolved?: string[];
    research_status?: string | null;
  }): Promise<Blob> => {
    const response = await fetch(`${API_URL}/research/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new ApiError(
        response.status,
        errorDetail(await response.text(), response.status),
      );
    }
    return response.blob();
  },
};
