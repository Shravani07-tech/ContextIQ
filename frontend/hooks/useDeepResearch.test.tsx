// Deep research (C11) in useChat: routes to the agent stream when
// Research mode is set to "deep", exposes live progress steps, and
// finalizes the structured result onto the assistant message. Also
// covers the progress/result components.

import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ResearchPanel, ResearchProgress } from "@/components/chat/research-progress";
import { ChatProvider, useChat } from "@/hooks/useChat";
import { api } from "@/lib/api";
import { createTestQueryClient, withQueryClient } from "@/lib/test-utils";
import type { AgentResearchResult } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  api: { chatStream: vi.fn(), researchStream: vi.fn(), agentResearchStream: vi.fn() },
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), info: vi.fn(), warning: vi.fn() } }));

type Callbacks = Parameters<typeof api.agentResearchStream>[1];

const RESULT: AgentResearchResult = {
  question: "How did revenue and costs change?",
  status: "PARTIAL",
  scope: "All Documents",
  answer: "## Summary\nRevenue grew [S1].",
  plan_method: "llm",
  subquestions: [
    { question: "How did revenue change?", status: "ANSWERED", queries: ["revenue"], source_labels: ["S1"] },
    { question: "How did costs change?", status: "UNRESOLVED", queries: ["costs", "cost trend"], source_labels: [], note: "No relevant passages were found in the selected scope." },
  ],
  unresolved: ["How did costs change?"],
  sources: [{ label: "S1", filename: "a.pdf", chunk_id: "a.pdf-0", similarity: 0.8 }],
  citation_verification: [],
  contradictions: [],
  evidence_assessment: null,
  steps: [],
  warnings: ["Retrieval limit reached before every sub-question was searched."],
  limits: { retrievals_used: 3, max_retrievals: 8, followups_used: 1, max_followups: 2, elapsed_seconds: 12.5 },
};

function renderChat() {
  const Q = withQueryClient(createTestQueryClient());
  return renderHook(() => useChat(), {
    wrapper: ({ children }) => (
      <Q>
        <ChatProvider>{children}</ChatProvider>
      </Q>
    ),
  });
}

describe("useChat deep research", () => {
  beforeEach(() => {
    vi.mocked(api.agentResearchStream).mockReset();
    vi.mocked(api.researchStream).mockReset();
    sessionStorage.clear();
  });

  it("streams progress and stores the structured result", async () => {
    const calls: Callbacks[] = [];
    vi.mocked(api.agentResearchStream).mockImplementation(async (_q, cb) => {
      calls.push(cb);
    });
    const { result } = renderChat();

    act(() => {
      result.current.setIsResearchMode(true);
      result.current.setResearchDepth("deep");
    });
    act(() => result.current.sendMessage("How did revenue and costs change?"));
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(api.researchStream).not.toHaveBeenCalled();

    act(() => calls[0].onProgress?.({ stage: "plan", message: "Planned 2 sub-question(s) (llm)." }));
    expect(result.current.researchSteps).toHaveLength(1);

    act(() => calls[0].onToken("## Summary\nRevenue grew [S1]."));
    act(() => calls[0].onResult(RESULT));
    act(() => calls[0].onDone());

    await waitFor(() => expect(result.current.isStreaming).toBe(false));
    const answer = result.current.messages[1];
    expect(answer.role).toBe("assistant");
    expect(answer.content).toContain("Revenue grew [S1]");
    expect(answer.research?.status).toBe("PARTIAL");
    expect(answer.research?.unresolved).toEqual(["How did costs change?"]);
    expect(answer.sources?.[0].filename).toBe("a.pdf");
    expect(answer.question).toBe("How did revenue and costs change?");
    expect(result.current.researchSteps).toHaveLength(0);
  });

  it("explains a run with no synthesized answer instead of showing nothing", async () => {
    const calls: Callbacks[] = [];
    vi.mocked(api.agentResearchStream).mockImplementation(async (_q, cb) => {
      calls.push(cb);
    });
    const { result } = renderChat();
    act(() => {
      result.current.setIsResearchMode(true);
      result.current.setResearchDepth("deep");
    });
    act(() => result.current.sendMessage("Anything about Mars?"));
    await waitFor(() => expect(calls).toHaveLength(1));
    act(() => calls[0].onResult({ ...RESULT, status: "FAILED", answer: "", sources: [] }));
    act(() => calls[0].onDone());
    await waitFor(() => expect(result.current.messages).toHaveLength(2));
    expect(result.current.messages[1].content).toMatch(/couldn't find relevant evidence/);
  });

  it("quick research keeps using the one-pass endpoint", async () => {
    vi.mocked(api.researchStream).mockImplementation(async () => {});
    const { result } = renderChat();
    act(() => result.current.setIsResearchMode(true));
    act(() => result.current.sendMessage("Summarize themes"));
    await waitFor(() => expect(api.researchStream).toHaveBeenCalledTimes(1));
    expect(api.agentResearchStream).not.toHaveBeenCalled();
  });
});

describe("research components", () => {
  it("ResearchProgress lists steps with found counts as a live status", () => {
    render(
      <ResearchProgress
        steps={[
          { stage: "plan", message: "Planned 2 sub-question(s) (llm)." },
          { stage: "retrieve", message: "Searched: revenue", found: 3 },
        ]}
      />,
    );
    expect(screen.getByRole("status", { name: "Research progress" })).toBeInTheDocument();
    expect(screen.getByText(/3 passages/)).toBeInTheDocument();
  });

  it("ResearchPanel shows statuses, unresolved questions and limits", async () => {
    const { answer: _a, sources: _s, citation_verification: _c, contradictions: _d, evidence_assessment: _e, ...research } = RESULT;
    void [_a, _s, _c, _d, _e];
    render(<ResearchPanel research={research} />);
    // PARTIAL runs open by default so gaps are not hidden.
    expect(screen.getByText("Evidence found")).toBeInTheDocument();
    expect(screen.getByText("No evidence")).toBeInTheDocument();
    expect(screen.getByText(/Little or no supporting evidence/)).toBeInTheDocument();
    expect(screen.getByText(/3\/8 searches/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /research process/i }));
    expect(screen.queryByText("Evidence found")).not.toBeInTheDocument();
  });
});
