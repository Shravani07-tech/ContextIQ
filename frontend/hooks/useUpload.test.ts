// Tests for useUpload: client-side validation, the upload->index
// chain, per-file server errors (including the orphaned-upload
// cleanup message), cancellation, and network-level failure handling.

import { act, renderHook, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { createTestQueryClient, withQueryClient } from "@/lib/test-utils";
import { useUpload } from "@/hooks/useUpload";
import type { UploadResponse } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  api: { upload: vi.fn(), index: vi.fn() },
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

function makeFile(name: string, sizeBytes = 100): File {
  const file = new File(["x".repeat(Math.min(sizeBytes, 1000))], name, {
    type: "text/plain",
  });
  // Fake a large size cheaply — allocating real 26 MB per test would
  // be wasteful; File.size is a getter we can override directly.
  Object.defineProperty(file, "size", { value: sizeBytes });
  return file;
}

/** api.upload now returns {promise, cancel} rather than a bare
    promise (so a real Cancel button has something to call) — these
    helpers keep the mocks matching that shape in one place. */
function mockUploadResolves(response: UploadResponse) {
  const cancel = vi.fn();
  vi.mocked(api.upload).mockReturnValue({
    promise: Promise.resolve(response),
    cancel,
  });
  return cancel;
}

function mockUploadRejects(error: Error) {
  const cancel = vi.fn();
  vi.mocked(api.upload).mockReturnValue({
    promise: Promise.reject(error),
    cancel,
  });
  return cancel;
}

beforeEach(() => {
  vi.mocked(api.upload).mockReset();
  vi.mocked(api.index).mockReset();
  vi.mocked(toast.error).mockClear();
  vi.mocked(toast.success).mockClear();
  vi.mocked(toast.info).mockClear();
});

function renderUpload(queryClient = createTestQueryClient()) {
  return { ...renderHook(() => useUpload(), { wrapper: withQueryClient(queryClient) }), queryClient };
}

describe("useUpload — client-side validation", () => {
  it("rejects an unsupported file extension without calling the API", () => {
    const { result } = renderUpload();

    result.current.uploadFiles([makeFile("malware.exe")]);

    expect(api.upload).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith(
      "Rejected malware.exe",
      expect.objectContaining({ description: expect.stringContaining("PDF and TXT") }),
    );
  });

  it("rejects a file over the 25 MB client-side cap without calling the API", () => {
    const { result } = renderUpload();

    result.current.uploadFiles([makeFile("huge.pdf", 26 * 1024 * 1024)]);

    expect(api.upload).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith(
      "Rejected huge.pdf",
      expect.objectContaining({ description: expect.stringContaining("25 MB") }),
    );
  });

  it("rejects an empty file without calling the API", () => {
    const { result } = renderUpload();

    result.current.uploadFiles([makeFile("empty.txt", 0)]);

    expect(api.upload).not.toHaveBeenCalled();
  });
});

describe("useUpload — upload -> index chain", () => {
  it("uploads then indexes valid files, and refreshes documents + status", async () => {
    mockUploadResolves({
      files: [{ filename: "notes.txt", status: "saved" }],
    });
    vi.mocked(api.index).mockResolvedValue({
      files: [{ filename: "notes.txt", status: "indexed", chunks_indexed: 3 }],
      vector_count: 10,
    });

    const { result, queryClient } = renderUpload();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    result.current.uploadFiles([makeFile("notes.txt")]);

    await waitFor(() => expect(result.current.isPending).toBe(false));

    expect(api.upload).toHaveBeenCalledTimes(1);
    expect(api.index).toHaveBeenCalledWith(["notes.txt"]);
    expect(toast.success).toHaveBeenCalledWith(
      "Indexed notes.txt",
      expect.objectContaining({ description: expect.stringContaining("3 chunk") }),
    );
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["documents"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["status"] });
    // A brief explicit "success" phase now precedes the settle to
    // idle (UI review item 3) — isPending going false lands here,
    // not at idle; see the dedicated revert-to-idle test below.
    expect(result.current.phase).toBe("success");
    expect(result.current.lastResults).toEqual([
      { filename: "notes.txt", status: "indexed", chunks_indexed: 3 },
    ]);
  });

  it("does not call /index when every uploaded file was rejected server-side", async () => {
    mockUploadResolves({
      files: [{ filename: "bad.pdf", status: "error", error: "corrupt" }],
    });

    const { result } = renderUpload();
    result.current.uploadFiles([makeFile("bad.pdf")]);

    await waitFor(() => expect(result.current.isPending).toBe(false));

    expect(api.index).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith(
      "Rejected bad.pdf",
      expect.objectContaining({ description: "corrupt" }),
    );
  });
});

describe("useUpload — server-side / API failure handling", () => {
  it("surfaces an orphaned-upload cleanup message when indexing fails", async () => {
    mockUploadResolves({
      files: [{ filename: "corrupt.pdf", status: "saved" }],
    });
    vi.mocked(api.index).mockResolvedValue({
      files: [
        {
          filename: "corrupt.pdf",
          status: "error",
          error: "EOF marker not found (the file has been removed — re-upload to retry)",
        },
      ],
      vector_count: 0,
    });

    const { result } = renderUpload();
    result.current.uploadFiles([makeFile("corrupt.pdf")]);

    await waitFor(() => expect(result.current.isPending).toBe(false));

    expect(toast.error).toHaveBeenCalledWith(
      "Failed to index corrupt.pdf",
      expect.objectContaining({
        description: expect.stringContaining("has been removed"),
      }),
    );
  });

  it("handles a network-level upload failure and resets to idle", async () => {
    mockUploadRejects(new Error("Backend is unreachable."));

    const { result } = renderUpload();
    result.current.uploadFiles([makeFile("notes.txt")]);

    await waitFor(() => expect(result.current.isPending).toBe(false));

    expect(toast.error).toHaveBeenCalledWith(
      "Upload failed",
      expect.objectContaining({ description: "Backend is unreachable." }),
    );
    // A brief explicit "error" phase now precedes the settle to idle
    // (UI review item 3), same as the success path above.
    expect(result.current.phase).toBe("error");
    expect(result.current.progress).toBe(0);
  });

  it("settles from the explicit success phase back to idle after the display delay", async () => {
    mockUploadResolves({
      files: [{ filename: "notes.txt", status: "saved" }],
    });
    vi.mocked(api.index).mockResolvedValue({
      files: [{ filename: "notes.txt", status: "indexed", chunks_indexed: 1 }],
      vector_count: 1,
    });

    const { result } = renderUpload();
    result.current.uploadFiles([makeFile("notes.txt")]);

    await waitFor(() => expect(result.current.phase).toBe("success"));

    // Real timers, real wait — simplest robust way to prove the
    // production setTimeout (OUTCOME_DISPLAY_MS) actually fires,
    // without the fake-timers/waitFor interaction pitfalls that come
    // from mixing the two.
    await waitFor(() => expect(result.current.phase).toBe("idle"), {
      timeout: 3000,
    });
  });
});

describe("useUpload — cancellation", () => {
  it("calls the upload's cancel handle when cancelUpload is invoked", async () => {
    // A promise that never resolves keeps the upload genuinely "in
    // flight" — an immediately-resolved mock finishes the whole
    // mutation (uploading -> settled -> idle) in under a
    // millisecond, faster than waitFor's polling can ever observe
    // the transient "uploading" phase.
    const cancel = vi.fn();
    vi.mocked(api.upload).mockReturnValue({
      promise: new Promise(() => {}),
      cancel,
    });

    const { result } = renderUpload();
    act(() => {
      result.current.uploadFiles([makeFile("notes.txt")]);
    });

    await waitFor(() => expect(result.current.phase).toBe("uploading"));

    result.current.cancelUpload();

    expect(cancel).toHaveBeenCalledTimes(1);
  });

  it("shows an info toast (not an error) when a cancelled upload rejects", async () => {
    mockUploadRejects(new Error("Upload cancelled."));

    const { result } = renderUpload();
    result.current.uploadFiles([makeFile("notes.txt")]);

    await waitFor(() => expect(result.current.isPending).toBe(false));

    expect(toast.info).toHaveBeenCalledWith("Upload cancelled");
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("is a no-op if there is no upload in flight", () => {
    const { result } = renderUpload();
    expect(() => result.current.cancelUpload()).not.toThrow();
  });
});
