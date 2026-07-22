// Tests for SourceCards — the citation disclosure under each answer.
// Two collapse levels: the "Sources · N" summary, and per-row preview
// expansion. Also covers chunk-number parsing from the chunk id.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { SourceCards } from "@/components/chat/source-cards";
import type { Source } from "@/lib/types";

const sources: Source[] = [
  {
    filename: "zephyra.txt",
    chunk_id: "zephyra.txt-3",
    similarity: 0.85,
    preview: "Zephyra stores knowledge in three tiers.",
  },
  { filename: "notes.txt", chunk_id: "notes.txt-0", similarity: 0.6 },
];

describe("SourceCards", () => {
  it("renders nothing when there are no sources", () => {
    const { container } = render(<SourceCards sources={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("is collapsed by default, showing only the summary count", () => {
    render(<SourceCards sources={sources} />);

    expect(
      screen.getByRole("button", { name: /Sources · 2/ }),
    ).toBeInTheDocument();
    expect(screen.queryByText("zephyra.txt")).not.toBeInTheDocument();
  });

  it("reveals the per-source rows with parsed chunk numbers when expanded", async () => {
    render(<SourceCards sources={sources} />);

    await userEvent.click(screen.getByRole("button", { name: /Sources · 2/ }));

    expect(screen.getByText("zephyra.txt")).toBeInTheDocument();
    // "zephyra.txt-3" -> "chunk 3" (filename itself may contain dashes).
    expect(screen.getByText("chunk 3")).toBeInTheDocument();
    expect(screen.getByText("chunk 0")).toBeInTheDocument();
  });

  it("expands a row that has a preview to reveal its snippet", async () => {
    render(<SourceCards sources={sources} />);

    await userEvent.click(screen.getByRole("button", { name: /Sources · 2/ }));
    // The first row carries a preview and is therefore expandable.
    await userEvent.click(
      screen.getByRole("button", { name: /zephyra\.txt/ }),
    );

    expect(
      screen.getByText("Zephyra stores knowledge in three tiers."),
    ).toBeInTheDocument();
  });
});
