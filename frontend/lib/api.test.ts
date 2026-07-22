// Tests for the HTTP layer (lib/api.ts): the hand-rolled SSE frame
// parser in chatStream (including frames split across network chunks),
// stream error events, deliberate cancellation, and the {detail}
// error-message normalization shared by the fetch-based methods.
//
// Only fetch is mocked — the real parsing/normalization code runs.

import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError } from "@/lib/api";
import type { Source } from "@/lib/types";

/** Build a ReadableStream that emits each string as its own network
    chunk, so tests can control exactly where the byte boundaries fall
    (the whole point of the buffering logic under test). */
function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

function okStream(chunks: string[]): Response {
  return { ok: true, body: streamOf(chunks) } as unknown as Response;
}

function collectCallbacks() {
  const sources: Source[][] = [];
  const tokens: string[] = [];
  const errors: string[] = [];
  let done = 0;
  return {
    sources,
    tokens,
    errors,
    get done() {
      return done;
    },
    callbacks: {
      onSources: (s: Source[]) => sources.push(s),
      onToken: (t: string) => tokens.push(t),
      onDone: () => {
        done += 1;
      },
      onError: (d: string) => errors.push(d),
    },
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("api.chatStream — SSE parsing", () => {
  it("dispatches sources, then tokens, then done, in order", async () => {
    const sources: Source[] = [
      { filename: "zephyra.txt", chunk_id: "zephyra.txt-3", similarity: 0.9 },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      okStream([
        `data: ${JSON.stringify({ type: "sources", sources })}\n\n`,
        `data: ${JSON.stringify({ type: "token", text: "Hello " })}\n\n`,
        `data: ${JSON.stringify({ type: "token", text: "world." })}\n\n`,
        `data: ${JSON.stringify({ type: "done" })}\n\n`,
      ]),
    );

    const c = collectCallbacks();
    await api.chatStream("q", c.callbacks, new AbortController().signal);

    expect(c.sources).toEqual([sources]);
    expect(c.tokens).toEqual(["Hello ", "world."]);
    expect(c.done).toBe(1);
    expect(c.errors).toEqual([]);
  });

  it("reassembles a frame that is split across two network chunks", async () => {
    // The token frame is delivered in two halves with the "\n\n"
    // separator only arriving in the second — the buffer must hold
    // the partial frame rather than parsing garbage.
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      okStream([
        `data: ${JSON.stringify({ type: "token", text: "split" }).slice(0, 10)}`,
        `${JSON.stringify({ type: "token", text: "split" }).slice(10)}\n\n`,
        `data: ${JSON.stringify({ type: "done" })}\n\n`,
      ]),
    );

    const c = collectCallbacks();
    await api.chatStream("q", c.callbacks, new AbortController().signal);

    expect(c.tokens).toEqual(["split"]);
    expect(c.done).toBe(1);
  });

  it("surfaces a stream error event and stops", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      okStream([
        `data: ${JSON.stringify({ type: "token", text: "partial" })}\n\n`,
        `data: ${JSON.stringify({ type: "error", detail: "Ollama is down" })}\n\n`,
        `data: ${JSON.stringify({ type: "token", text: "never" })}\n\n`,
      ]),
    );

    const c = collectCallbacks();
    await api.chatStream("q", c.callbacks, new AbortController().signal);

    expect(c.tokens).toEqual(["partial"]);
    expect(c.errors).toEqual(["Ollama is down"]);
    expect(c.done).toBe(0);
  });

  it("treats a stream that closes without a done event as complete", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      okStream([`data: ${JSON.stringify({ type: "token", text: "hi" })}\n\n`]),
    );

    const c = collectCallbacks();
    await api.chatStream("q", c.callbacks, new AbortController().signal);

    expect(c.tokens).toEqual(["hi"]);
    expect(c.done).toBe(1);
  });

  it("reports the backend {detail} message on a non-OK response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 503,
      text: async () => JSON.stringify({ detail: "Model is warming up" }),
    } as unknown as Response);

    const c = collectCallbacks();
    await api.chatStream("q", c.callbacks, new AbortController().signal);

    expect(c.errors).toEqual(["Model is warming up"]);
  });

  it("stays silent when the caller aborts (it already knows it stopped)", async () => {
    const controller = new AbortController();
    controller.abort();
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      new DOMException("aborted", "AbortError"),
    );

    const c = collectCallbacks();
    await api.chatStream("q", c.callbacks, controller.signal);

    expect(c.errors).toEqual([]);
    expect(c.tokens).toEqual([]);
    expect(c.done).toBe(0);
  });

  it("reports an unreachable backend when fetch fails without an abort", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("network"));

    const c = collectCallbacks();
    await api.chatStream("q", c.callbacks, new AbortController().signal);

    expect(c.errors).toEqual(["Backend is unreachable. Is the API running?"]);
  });
});

describe("api error normalization", () => {
  it("extracts the FastAPI {detail} from a failed request", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 404,
      text: async () => JSON.stringify({ detail: "Document not found" }),
    } as unknown as Response);

    await expect(api.deleteDocument("missing.txt")).rejects.toMatchObject({
      status: 404,
      message: "Document not found",
    });
  });

  it("falls back to a generic message for a non-JSON error body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 500,
      text: async () => "<html>Internal Server Error</html>",
    } as unknown as Response);

    await expect(api.documents()).rejects.toMatchObject({
      status: 500,
      message: "Request failed (500)",
    });
  });

  it("maps a network-level failure to ApiError status 0", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("network"));

    const error = await api.documents().catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(0);
  });
});
