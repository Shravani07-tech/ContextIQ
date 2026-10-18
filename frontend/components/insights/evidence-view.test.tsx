// Evidence assessment UI (C8): summary counts, expandable reasons and
// passages, the non-probability disclaimer, the claim-check dialog, and
// the SSE event wiring in api.chatStream.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EvidencePanel } from "@/components/insights/evidence-view";
import type { ClaimAssessment, EvidenceAssessment } from "@/lib/types";

const CLAIM: ClaimAssessment = {
  claim: "Revenue grew 25% in 2024.",
  rating: "STRONG",
  basis: "model-assisted",
  factors: { relevance: "HIGH", directness: "DIRECT", independent_sources: 2, duplicates_collapsed: 1, contradiction: "NONE" },
  explanation: ["The citation check found the passages directly support the claim."],
  passages: [
    { filename: "annual.pdf", chunk_id: "annual.pdf-0", page: 4, relevance: "HIGH", cited_by_check: true, source_group: "annual.pdf" },
  ],
  contradictions: [],
};

const ASSESSMENT: EvidenceAssessment = {
  claims: [CLAIM, { ...CLAIM, claim: "Margins fell.", rating: "CONTESTED" }],
  counts: { STRONG: 1, MODERATE: 0, LIMITED: 0, CONTESTED: 1, UNSUPPORTED: 0, INSUFFICIENT: 0 },
  overall: "Some claims are contested by conflicting sources.",
  documents_considered: 2,
  independent_sources: 2,
  disclaimer: "Evidence ratings are rule-based ... not calibrated probabilities.",
};

describe("EvidencePanel", () => {
  it("renders nothing without an assessment", () => {
    const { container } = render(<EvidencePanel assessment={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("summarises ratings and expands to reasons, factors, passages, disclaimer", async () => {
    render(<EvidencePanel assessment={ASSESSMENT} />);
    expect(screen.getByText("1 strong")).toBeInTheDocument();
    expect(screen.getByText("1 contested")).toBeInTheDocument();
    expect(screen.queryByText(/calibrated probabilities/)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /evidence assessment/i }));
    expect(screen.getByText(/calibrated probabilities/)).toBeInTheDocument();
    expect(screen.getByText("Some claims are contested by conflicting sources.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Revenue grew 25% in 2024/ }));
    expect(screen.getByText(/directly support the claim/)).toBeInTheDocument();
    expect(screen.getByText("2 (+1 duplicate)")).toBeInTheDocument();
    expect(screen.getByText("p. 4")).toBeInTheDocument();
    // No percentages anywhere: ratings are categorical by design.
    expect(document.body.textContent).not.toMatch(/\d+%\s*(confidence|probability)/i);
  });
});

describe("api.chatStream evidence event", () => {
  afterEach(() => vi.restoreAllMocks());

  it("dispatches evidence_assessment frames", async () => {
    const { api } = await import("@/lib/api");
    const frames = [
      `data: ${JSON.stringify({ type: "sources", sources: [] })}\n\n`,
      `data: ${JSON.stringify({ type: "evidence_assessment", assessment: ASSESSMENT })}\n\n`,
      `data: ${JSON.stringify({ type: "done" })}\n\n`,
    ];
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      start(c) {
        frames.forEach((f) => c.enqueue(encoder.encode(f)));
        c.close();
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, body } as unknown as Response);
    const onEvidenceAssessment = vi.fn();
    await api.chatStream(
      "q",
      { onSources: vi.fn(), onToken: vi.fn(), onDone: vi.fn(), onError: vi.fn(), onEvidenceAssessment },
      new AbortController().signal,
    );
    expect(onEvidenceAssessment).toHaveBeenCalledWith(ASSESSMENT);
  });
});

const mocks = vi.hoisted(() => ({ assessEvidence: vi.fn() }));

describe("EvidenceDialog", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("checks a statement and shows the rated result with warnings", async () => {
    vi.doMock("@/lib/api", () => ({
      api: {
        assessEvidence: mocks.assessEvidence,
        detailedDocuments: vi.fn().mockResolvedValue({ documents: [] }),
        collections: vi.fn().mockResolvedValue({ collections: [] }),
      },
    }));
    mocks.assessEvidence.mockResolvedValue({
      claim: CLAIM.claim,
      scope: "All Documents",
      assessment: { ...CLAIM, rating: "LIMITED", basis: "heuristic" },
      disclaimer: "Not calibrated probabilities.",
      model_checked: false,
      warnings: ["The local model did not return a citation check."],
    });
    const { EvidenceDialog } = await import("@/components/insights/evidence-dialog");
    const { createTestQueryClient, withQueryClient } = await import("@/lib/test-utils");
    const Wrapper = withQueryClient(createTestQueryClient());
    render(
      <Wrapper>
        <EvidenceDialog />
      </Wrapper>,
    );

    await userEvent.click(screen.getByRole("button", { name: /check a claim/i }));
    const checkButton = await screen.findByRole("button", { name: /check evidence/i });
    expect(checkButton).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Statement to check"), CLAIM.claim);
    await userEvent.click(checkButton);

    expect(await screen.findByText("Limited")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/did not return a citation check/);
    expect(screen.getByText(/keyword overlap only/)).toBeInTheDocument();
    expect(mocks.assessEvidence).toHaveBeenCalledWith({ claim: CLAIM.claim, collection_id: null, filenames: null });
  });
});
