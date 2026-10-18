// Knowledge graph explorer (C10): empty/unbuilt state, building, entity
// list + details with supported vs uncertain relationships, and the
// deterministic layout helper.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GraphDialog } from "@/components/insights/graph-dialog";
import { layoutGraph } from "@/lib/graph-layout";
import { createTestQueryClient, withQueryClient } from "@/lib/test-utils";
import type { GraphResponse } from "@/lib/types";

const mocks = vi.hoisted(() => ({
  graph: vi.fn(),
  buildGraph: vi.fn(),
  graphEntity: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    graph: mocks.graph,
    buildGraph: mocks.buildGraph,
    graphEntity: mocks.graphEntity,
    detailedDocuments: vi.fn().mockResolvedValue({ documents: [] }),
    collections: vi.fn().mockResolvedValue({ collections: [] }),
  },
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), warning: vi.fn(), error: vi.fn() } }));

const EMPTY: GraphResponse = {
  scope: "All Documents", documents_in_scope: 2, documents_extracted: 0, extractions: [],
  nodes: [], edges: [], truncated: false, total_entities: 0, possible_duplicates: [],
};

const BUILT: GraphResponse = {
  ...EMPTY,
  documents_extracted: 2,
  extractions: [
    { filename: "a.txt", status: "completed", method: "llm", chunks_analyzed: 2, entity_count: 2, relation_count: 1 },
  ],
  nodes: [
    { id: "e1", name: "Jane Doe", type: "PERSON", mentions: 3, documents: 1, degree: 1 },
    { id: "e2", name: "Acme Corp", type: "ORGANIZATION", mentions: 2, documents: 1, degree: 1 },
  ],
  edges: [{ id: "e1|founded|e2", source: "e1", target: "e2", relation: "founded", status: "SUPPORTED", evidence_count: 1 }],
  total_entities: 2,
  possible_duplicates: [{ a: "e2", b: "e3", a_name: "Acme Corp", b_name: "Acme", reason: "One name contains the other" }],
};

function renderDialog() {
  const Wrapper = withQueryClient(createTestQueryClient());
  return render(
    <Wrapper>
      <GraphDialog />
    </Wrapper>,
  );
}

describe("GraphDialog", () => {
  beforeEach(() => {
    mocks.graph.mockReset();
    mocks.buildGraph.mockReset();
    mocks.graphEntity.mockReset();
  });

  it("explains an unbuilt graph and processes the documents in scope", async () => {
    mocks.graph.mockResolvedValueOnce(EMPTY).mockResolvedValue(BUILT);
    mocks.buildGraph.mockResolvedValue({ scope: "All Documents", processed: [], remaining: 0 });
    renderDialog();

    await userEvent.click(screen.getByRole("button", { name: /graph/i }));
    expect(await screen.findByText(/hasn't been built/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /process 2 documents/i }));
    await waitFor(() => expect(mocks.buildGraph).toHaveBeenCalledWith({ collection_id: null, filenames: null, force: false }));
    const list = await screen.findByRole("list", { name: "Entities" });
    expect(within(list).getByRole("button", { name: /Jane Doe/ })).toBeInTheDocument();
    // The SVG node is focusable with a descriptive label too.
    expect(screen.getByRole("button", { name: "Jane Doe, person, 3 mentions" })).toBeInTheDocument();
    expect(screen.getByText(/possible duplicate/)).toBeInTheDocument();
  });

  it("shows entity details with relationship status and sources", async () => {
    mocks.graph.mockResolvedValue(BUILT);
    mocks.graphEntity.mockResolvedValue({
      entity: { id: "e1", name: "Jane Doe", type: "PERSON" },
      mentions: [{ surface: "Jane Doe", source: { filename: "a.txt", chunk_id: "a.txt-0", page: 2 } }],
      relations: [
        { id: "r1", relation: "founded", status: "SUPPORTED", direction: "outgoing",
          other: { id: "e2", name: "Acme Corp", type: "ORGANIZATION" },
          evidence: "Jane Doe founded Acme Corp", source: { filename: "a.txt", chunk_id: "a.txt-0", page: 2 } },
        { id: "r2", relation: "located in", status: "UNCERTAIN", direction: "outgoing",
          other: { id: "e4", name: "Berlin", type: "PLACE" },
          evidence: null, source: { filename: "a.txt", chunk_id: "a.txt-0" } },
      ],
      documents: ["a.txt"],
    });
    renderDialog();

    await userEvent.click(screen.getByRole("button", { name: /graph/i }));
    const list = await screen.findByRole("list", { name: "Entities" });
    await userEvent.click(within(list).getByRole("button", { name: /Jane Doe/ }));

    expect(await screen.findByText("Supported")).toBeInTheDocument();
    expect(screen.getByText("Uncertain")).toBeInTheDocument();
    expect(screen.getByText("“Jane Doe founded Acme Corp”")).toBeInTheDocument();
    expect(screen.getAllByText("p. 2").length).toBeGreaterThan(0);
    expect(mocks.graphEntity).toHaveBeenCalledWith("e1", { collection_id: null, filenames: null });
  });

  it("surfaces load errors with retry", async () => {
    mocks.graph.mockRejectedValueOnce(new Error("Collection not found."));
    renderDialog();
    await userEvent.click(screen.getByRole("button", { name: /graph/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Collection not found.");
  });
});

describe("layoutGraph", () => {
  it("is deterministic and keeps nodes inside the canvas", () => {
    const nodes = Array.from({ length: 30 }, (_, i) => ({ id: `n${i}` }));
    const edges = nodes.slice(1).map((n, i) => ({ source: `n${i}`, target: n.id }));
    const a = layoutGraph(nodes, edges, 640, 420);
    const b = layoutGraph(nodes, edges, 640, 420);
    expect([...a.entries()]).toEqual([...b.entries()]);
    for (const p of a.values()) {
      expect(p.x).toBeGreaterThanOrEqual(24);
      expect(p.x).toBeLessThanOrEqual(616);
      expect(p.y).toBeGreaterThanOrEqual(24);
      expect(p.y).toBeLessThanOrEqual(396);
    }
    expect(layoutGraph([], [], 100, 100).size).toBe(0);
  });
});
