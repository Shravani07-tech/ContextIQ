// Tests for useChat: streaming a question to a grounded answer,
// stopping generation mid-stream, regenerating the last answer,
// clearing the conversation, API-failure handling, the
// pending-request guard, and session persistence.

import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { createTestQueryClient, withQueryClient } from "@/lib/test-utils";
import { ChatProvider, useChat } from "@/hooks/useChat";
import type { Source } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  api: { chatStream: vi.fn() },
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

interface StreamCallbacks {
  onSources: (sources: Source[]) => void;
  onToken: (text: string) => void;
  onDone: () => void;
  onError: (detail: string) => void;
}

/** Captures the callbacks passed to api.chatStream for a given call
    so a test can drive them manually (simulating tokens arriving
    over time) instead of the mock resolving everything at once. */
function captureStream() {
  const calls: { question: string; callbacks: StreamCallbacks }[] = [];
  vi.mocked(api.chatStream).mockImplementation(
    async (question, callbacks) => {
      calls.push({ question, callbacks });
    },
  );
  return calls;
}

function renderChat() {
  const queryClient = createTestQueryClient();
  const QueryWrapper = withQueryClient(queryClient);
  return renderHook(() => useChat(), {
    wrapper: ({ children }) => (
      <QueryWrapper>
        <ChatProvider>{children}</ChatProvider>
      </QueryWrapper>
    ),
  });
}

beforeEach(() => {
  vi.mocked(api.chatStream).mockReset();
  sessionStorage.clear();
});

describe("useChat — streaming", () => {
  it("sends a question and streams the answer in, finalizing with its sources", async () => {
    const calls = captureStream();
    const { result } = renderChat();

    act(() => result.current.sendMessage("How does Zephyra store knowledge?"));

    // User message appears immediately, before any stream events.
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]).toMatchObject({
      role: "user",
      content: "How does Zephyra store knowledge?",
    });

    await waitFor(() => expect(calls).toHaveLength(1));
    expect(result.current.isThinking).toBe(true);

    const sources: Source[] = [
      { filename: "zephyra.txt", chunk_id: "zephyra.txt-3", similarity: 0.85 },
    ];
    act(() => calls[0].callbacks.onSources(sources));
    act(() => calls[0].callbacks.onToken("Zephyra stores "));
    await waitFor(() => expect(result.current.isStreaming).toBe(true));
    expect(result.current.streamingContent).toBe("Zephyra stores ");

    act(() => calls[0].callbacks.onToken("knowledge in three tiers."));
    act(() => calls[0].callbacks.onDone());

    await waitFor(() => expect(result.current.isStreaming).toBe(false));
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[1]).toMatchObject({
      role: "assistant",
      content: "Zephyra stores knowledge in three tiers.",
    });
    expect(result.current.lastSources).toEqual(sources);
    // Streaming scratch state is cleared once finalized.
    expect(result.current.streamingContent).toBe("");
  });

  it("ignores blank and whitespace-only questions", () => {
    captureStream();
    const { result } = renderChat();

    act(() => result.current.sendMessage("   "));

    expect(result.current.messages).toHaveLength(0);
    expect(api.chatStream).not.toHaveBeenCalled();
  });

  it("does not send a second question while one is still streaming", async () => {
    const calls = captureStream();
    const { result } = renderChat();

    act(() => result.current.sendMessage("first question"));
    await waitFor(() => expect(calls).toHaveLength(1));
    act(() => calls[0].callbacks.onToken("partial answer"));
    await waitFor(() => expect(result.current.isStreaming).toBe(true));

    act(() => result.current.sendMessage("second question")); // should be dropped
    expect(calls).toHaveLength(1);

    act(() => calls[0].callbacks.onDone());
    await waitFor(() => expect(result.current.isStreaming).toBe(false));
    expect(result.current.messages).toHaveLength(2); // one user, one assistant
  });
});

describe("useChat — stop generation", () => {
  it("keeps the partial answer as the final message when stopped mid-stream", async () => {
    const calls = captureStream();
    const { result } = renderChat();

    act(() => result.current.sendMessage("a question"));
    await waitFor(() => expect(calls).toHaveLength(1));
    act(() => calls[0].callbacks.onToken("Partial answer so far."));
    await waitFor(() => expect(result.current.isStreaming).toBe(true));

    act(() => result.current.stopGeneration());

    expect(result.current.isStreaming).toBe(false);
    expect(result.current.isThinking).toBe(false);
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[1]).toMatchObject({
      role: "assistant",
      content: "Partial answer so far.",
    });
  });

  it("adds a 'Generation stopped' notice when stopped before any tokens arrive", async () => {
    const calls = captureStream();
    const { result } = renderChat();

    act(() => result.current.sendMessage("a question"));
    await waitFor(() => expect(calls).toHaveLength(1));
    // Still thinking — no tokens yet.
    act(() => result.current.stopGeneration());

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[1]).toMatchObject({
      role: "system",
      content: "Generation stopped",
    });
  });

  it("is a no-op if nothing is generating", () => {
    captureStream();
    const { result } = renderChat();
    expect(() => result.current.stopGeneration()).not.toThrow();
    expect(result.current.messages).toHaveLength(0);
  });
});

describe("useChat — regenerate", () => {
  it("replaces the last answer in place without duplicating the question", async () => {
    const calls = captureStream();
    const { result } = renderChat();

    act(() => result.current.sendMessage("a question"));
    await waitFor(() => expect(calls).toHaveLength(1));
    act(() => calls[0].callbacks.onToken("first attempt"));
    act(() => calls[0].callbacks.onDone());
    await waitFor(() => expect(result.current.messages).toHaveLength(2));

    act(() => result.current.regenerate());
    await waitFor(() => expect(calls).toHaveLength(2));
    // The old answer is gone, the user question is not duplicated.
    expect(result.current.messages).toHaveLength(1);
    expect(calls[1].question).toBe("a question");

    act(() => calls[1].callbacks.onToken("second attempt"));
    act(() => calls[1].callbacks.onDone());
    await waitFor(() => expect(result.current.messages).toHaveLength(2));
    expect(result.current.messages[1].content).toBe("second attempt");
  });

  it("does nothing when there is no prior question", () => {
    captureStream();
    const { result } = renderChat();
    act(() => result.current.regenerate());
    expect(api.chatStream).not.toHaveBeenCalled();
  });
});

describe("useChat — clear conversation", () => {
  it("empties the transcript and resets in-flight state", async () => {
    const calls = captureStream();
    const { result } = renderChat();

    act(() => result.current.sendMessage("a question"));
    await waitFor(() => expect(calls).toHaveLength(1));
    act(() => calls[0].callbacks.onToken("still going"));
    await waitFor(() => expect(result.current.isStreaming).toBe(true));

    act(() => result.current.clearConversation());

    expect(result.current.messages).toHaveLength(0);
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.isThinking).toBe(false);
    expect(result.current.streamingContent).toBe("");
  });
});

describe("useChat — API failure handling", () => {
  it("records a failed answer as a system message instead of crashing", async () => {
    const calls = captureStream();
    const { result } = renderChat();

    act(() => result.current.sendMessage("any question"));
    await waitFor(() => expect(calls).toHaveLength(1));
    act(() =>
      calls[0].callbacks.onError("Backend is unreachable. Is the API running?"),
    );

    await waitFor(() => expect(result.current.isThinking).toBe(false));
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[1]).toMatchObject({ role: "system" });
    expect(result.current.messages[1].content).toContain("Backend is unreachable");
    expect(result.current.messages[1].retryQuestion).toBe("any question");
  });

  it("keeps partial tokens as a real answer AND reports the error if the stream breaks midway", async () => {
    const calls = captureStream();
    const { result } = renderChat();

    act(() => result.current.sendMessage("any question"));
    await waitFor(() => expect(calls).toHaveLength(1));
    act(() => calls[0].callbacks.onToken("Partial before the drop."));
    act(() => calls[0].callbacks.onError("The connection was interrupted mid-answer."));

    await waitFor(() => expect(result.current.messages).toHaveLength(3));
    expect(result.current.messages[1]).toMatchObject({
      role: "assistant",
      content: "Partial before the drop.",
    });
    expect(result.current.messages[2]).toMatchObject({ role: "system" });
  });
});

describe("useChat — session persistence", () => {
  it("restores the conversation from sessionStorage after a simulated reload", async () => {
    const calls = captureStream();
    const first = renderChat();

    act(() => first.result.current.sendMessage("remember this"));
    await waitFor(() => expect(calls).toHaveLength(1));
    act(() => calls[0].callbacks.onToken("Persisted answer."));
    act(() => calls[0].callbacks.onDone());
    await waitFor(() => expect(first.result.current.messages).toHaveLength(2));

    // Unmount (tab stays open, e.g. navigating away and back) and
    // mount a brand-new provider instance — simulates a page
    // refresh reading from sessionStorage rather than React state.
    first.unmount();
    const second = renderChat();

    await waitFor(() =>
      expect(second.result.current.messages).toHaveLength(2),
    );
    expect(second.result.current.messages[0].content).toBe("remember this");
    expect(second.result.current.messages[1].content).toBe("Persisted answer.");
  });

  it("starts fresh when sessionStorage is empty", () => {
    captureStream();
    const { result } = renderChat();
    expect(result.current.messages).toHaveLength(0);
  });
});
