// Timeline dialog (C7): builds a timeline through the API, renders dated
// and undated events with certainty labels and source locators, and
// surfaces errors with a retry.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TimelineDialog, timelineToMarkdown } from "@/components/insights/timeline-dialog";
import { createTestQueryClient, withQueryClient } from "@/lib/test-utils";
import type { TimelineResponse } from "@/lib/types";

const mocks = vi.hoisted(() => ({
  timeline: vi.fn(),
  detailedDocuments: vi.fn(),
  collections: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    timeline: mocks.timeline,
    detailedDocuments: mocks.detailedDocuments,
    collections: mocks.collections,
    exportResearchReport: vi.fn(),
  },
  ApiError: class extends Error {},
}));

const RESULT: TimelineResponse = {
  scope: "All Documents",
  focus: null,
  events: [
    {
      id: "evt-1",
      date: { text: "March 2019", start: "2019-03", end: "2019-03", precision: "month", certainty: "EXACT", in_source: true },
      date_type: "EVENT",
      description: "Acme Corp was founded.",
      actors: ["Jane Doe"],
      source: { filename: "history.pdf", chunk_id: "history.pdf-0", page: 3, preview: "Acme Corp was founded in March 2019." },
    },
  ],
  undated_events: [
    {
      id: "evt-2",
      date: { text: "last year", start: null, end: null, precision: "unknown", certainty: "RELATIVE", in_source: true },
      date_type: "EVENT",
      description: "Output doubled.",
      actors: [],
      source: { filename: "history.pdf", chunk_id: "history.pdf-2" },
    },
  ],
  document_dates: [{ filename: "history.pdf", indexed_at: "2026-01-01T00:00:00Z" }],
  extraction_method: "llm",
  chunks_analyzed: 2,
  documents_analyzed: 1,
  events_discarded: 0,
  warnings: [],
};

function renderDialog() {
  const client = createTestQueryClient();
  const Wrapper = withQueryClient(client);
  return render(
    <Wrapper>
      <TimelineDialog />
    </Wrapper>,
  );
}

describe("TimelineDialog", () => {
  beforeEach(() => {
    mocks.timeline.mockReset();
    mocks.detailedDocuments.mockResolvedValue({ documents: [] });
    mocks.collections.mockResolvedValue({ collections: [] });
  });

  it("builds and renders dated and undated events with sources", async () => {
    mocks.timeline.mockResolvedValue(RESULT);
    renderDialog();

    await userEvent.click(screen.getByRole("button", { name: /timeline/i }));
    await userEvent.click(await screen.findByRole("button", { name: /build timeline/i }));

    expect(await screen.findByText("Acme Corp was founded.")).toBeInTheDocument();
    expect(screen.getByText("Exact")).toBeInTheDocument();
    expect(screen.getByText("Relative")).toBeInTheDocument();
    expect(screen.getByText(/not placed on the timeline/i)).toBeInTheDocument();
    expect(screen.getByText("p. 3")).toBeInTheDocument();
    expect(mocks.timeline).toHaveBeenCalledWith({ collection_id: null, filenames: null, focus: null });
  });

  it("shows an error with retry when extraction fails", async () => {
    mocks.timeline.mockRejectedValueOnce(new Error("Collection not found."));
    renderDialog();

    await userEvent.click(screen.getByRole("button", { name: /timeline/i }));
    await userEvent.click(await screen.findByRole("button", { name: /build timeline/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Collection not found.");
    mocks.timeline.mockResolvedValueOnce(RESULT);
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Acme Corp was founded.")).toBeInTheDocument();
  });

  it("renders a markdown export that keeps certainty and locators", () => {
    const md = timelineToMarkdown(RESULT);
    expect(md).toContain("**March 2019** (exact)");
    expect(md).toContain("history.pdf, p. 3");
    expect(md).toContain("Events without a usable date");
  });
});
