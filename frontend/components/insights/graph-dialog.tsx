"use client";

// Knowledge graph explorer (C10). Entities and relationships extracted
// from the documents in scope, every one traceable to a passage.
// Supported relationships (quote found in the passage) are solid lines;
// uncertain ones are dashed and labelled as such. The searchable entity
// list is the keyboard/screen-reader path; the SVG is a visual overview
// whose nodes are also focusable.

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, Network, RefreshCw, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ScopePicker } from "@/components/insights/scope-picker";
import { SourceLocator } from "@/components/insights/source-locator";
import { ToneBadge } from "@/components/insights/tone-badge";
import { InlineError } from "@/components/shared/inline-error";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useActiveCollection } from "@/hooks/useCollections";
import { api } from "@/lib/api";
import { layoutGraph } from "@/lib/graph-layout";
import type { GraphResponse, ScopeParams } from "@/lib/types";
import { cn } from "@/lib/utils";

// Categorical palette for entity types. The theme's chart tokens are
// all shades of one blue, which can't distinguish seven categories;
// these hues are separable on the (dark-only) canvas and every type is
// also named in the legend and in each node's accessible label.
const TYPE_COLOR: Record<string, string> = {
  PERSON: "#60a5fa",
  ORGANIZATION: "#34d399",
  PLACE: "#fbbf24",
  PROJECT: "#c084fc",
  EVENT: "#f472b6",
  CONCEPT: "#22d3ee",
  OTHER: "#8b8b93",
};

const W = 640;
const H = 420;

function GraphCanvas({
  graph,
  selected,
  onSelect,
}: {
  graph: GraphResponse;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const positions = useMemo(() => layoutGraph(graph.nodes, graph.edges, W, H), [graph]);
  const maxMentions = Math.max(1, ...graph.nodes.map((n) => n.mentions));
  const linked = new Set(
    graph.edges.flatMap((e) => (e.source === selected || e.target === selected ? [e.source, e.target] : [])),
  );

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full rounded-lg border border-border bg-card"
      role="group"
      aria-label={`Knowledge graph with ${graph.nodes.length} entities and ${graph.edges.length} relationships`}
    >
      {graph.edges.map((e) => {
        const a = positions.get(e.source);
        const b = positions.get(e.target);
        if (!a || !b) return null;
        const active = selected && (e.source === selected || e.target === selected);
        return (
          <g key={e.id}>
            <line
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={active ? "var(--ring)" : "var(--border)"}
              strokeOpacity={active ? 0.9 : 1}
              strokeWidth={active ? 1.6 : 1}
              strokeDasharray={e.status === "UNCERTAIN" ? "4 3" : undefined}
            />
            {active && (
              <text
                x={(a.x + b.x) / 2}
                y={(a.y + b.y) / 2 - 3}
                textAnchor="middle"
                fontSize="9"
                fill="var(--muted-foreground)"
              >
                {e.relation}
              </text>
            )}
          </g>
        );
      })}
      {graph.nodes.map((n) => {
        const p = positions.get(n.id)!;
        const r = 4 + 6 * Math.sqrt(n.mentions / maxMentions);
        const isSel = n.id === selected;
        const dim = selected && !isSel && !linked.has(n.id);
        return (
          <g
            key={n.id}
            role="button"
            tabIndex={0}
            aria-label={`${n.name}, ${n.type.toLowerCase()}, ${n.mentions} mentions`}
            aria-pressed={isSel}
            onClick={() => onSelect(n.id)}
            onKeyDown={(ev) => {
              if (ev.key === "Enter" || ev.key === " ") {
                ev.preventDefault();
                onSelect(n.id);
              }
            }}
            className="cursor-pointer outline-none [&:focus-visible>circle]:stroke-[var(--ring)] [&:focus-visible>circle]:stroke-[3]"
            opacity={dim ? 0.35 : 1}
          >
            <circle
              cx={p.x}
              cy={p.y}
              r={r}
              fill={TYPE_COLOR[n.type] ?? TYPE_COLOR.OTHER}
              stroke={isSel ? "var(--foreground)" : "var(--background)"}
              strokeWidth={isSel ? 2 : 1}
            />
            {(isSel || linked.has(n.id) || n.degree >= 2 || graph.nodes.length <= 25) && (
              <text x={p.x + r + 3} y={p.y + 3} fontSize="10" fill="var(--foreground)">
                {n.name.length > 24 ? `${n.name.slice(0, 23)}…` : n.name}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

function EntityDetails({ id, scope, onBack, onSelect }: {
  id: string;
  scope: ScopeParams;
  onBack: () => void;
  onSelect: (id: string) => void;
}) {
  const detail = useQuery({
    queryKey: ["graph-entity", id, scope],
    queryFn: () => api.graphEntity(id, scope),
  });

  return (
    <div className="flex flex-col gap-3">
      <button type="button" onClick={onBack} className="flex items-center gap-1 self-start text-xs text-primary hover:underline">
        <ArrowLeft className="size-3" aria-hidden /> All entities
      </button>
      {detail.isPending ? (
        <Skeleton className="h-32 w-full rounded-lg" />
      ) : detail.isError ? (
        <InlineError message={detail.error.message} onRetry={() => detail.refetch()} />
      ) : (
        <>
          <div>
            <h3 className="text-sm font-semibold">{detail.data.entity.name}</h3>
            <p className="text-xs text-muted-foreground">
              {detail.data.entity.type.toLowerCase()} · {detail.data.mentions.length} mention
              {detail.data.mentions.length === 1 ? "" : "s"} in {detail.data.documents.length} document
              {detail.data.documents.length === 1 ? "" : "s"}
            </p>
          </div>
          <section aria-label="Relationships" className="space-y-1.5">
            <h4 className="text-xs font-bold uppercase tracking-[0.06em] text-muted-foreground">Relationships</h4>
            {detail.data.relations.length === 0 ? (
              <p className="text-xs text-muted-foreground">No relationships extracted for this entity.</p>
            ) : (
              <ul className="space-y-2">
                {detail.data.relations.map((r) => (
                  <li key={r.id} className="rounded-md border border-border p-2 text-xs">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {r.direction === "incoming" && (
                        <button type="button" className="font-medium text-primary hover:underline" onClick={() => onSelect(r.other.id)}>
                          {r.other.name}
                        </button>
                      )}
                      {r.direction === "incoming" ? null : <span className="font-medium">{detail.data.entity.name}</span>}
                      <span className="text-muted-foreground">{r.relation}</span>
                      {r.direction === "outgoing" ? (
                        <button type="button" className="font-medium text-primary hover:underline" onClick={() => onSelect(r.other.id)}>
                          {r.other.name}
                        </button>
                      ) : (
                        <span className="font-medium">{detail.data.entity.name}</span>
                      )}
                      <ToneBadge
                        tone={r.status === "SUPPORTED" ? "success" : "warning"}
                        title={
                          r.status === "SUPPORTED"
                            ? "The supporting quote was found in the passage."
                            : "Not confirmed: the passage mentions both, but no exact supporting quote was found."
                        }
                      >
                        {r.status === "SUPPORTED" ? "Supported" : "Uncertain"}
                      </ToneBadge>
                    </div>
                    {r.evidence && <p className="mt-1 italic text-muted-foreground">“{r.evidence}”</p>}
                    <SourceLocator source={r.source} className="mt-1" />
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section aria-label="Mentions" className="space-y-1.5">
            <h4 className="text-xs font-bold uppercase tracking-[0.06em] text-muted-foreground">Mentions</h4>
            <ul className="space-y-1.5">
              {detail.data.mentions.map((m) => (
                <li key={m.source.chunk_id}>
                  <SourceLocator source={m.source} />
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}

export function GraphDialog({ trigger }: { trigger?: React.ReactElement }) {
  const [open, setOpen] = useState(false);
  const [activeCollectionId] = useActiveCollection();
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [building, setBuilding] = useState(false);
  const qc = useQueryClient();

  const scope: ScopeParams = {
    collection_id: activeCollectionId,
    filenames: selectedDocs.length ? selectedDocs : null,
  };
  const graph = useQuery({
    queryKey: ["graph", scope],
    queryFn: () => api.graph(scope),
    enabled: open,
  });

  async function build(force = false) {
    setBuilding(true);
    try {
      let remaining = 0;
      let failed = 0;
      // The backend processes a small batch (3 documents by default) per
      // call so no single request runs for long; keep going until the
      // scope is done (or nothing is progressing).
      for (let round = 0; round < 10; round++) {
        const res = await api.buildGraph({ ...scope, force: force && round === 0 });
        failed += res.processed.filter((p) => p.status === "failed").length;
        remaining = res.remaining;
        if (remaining === 0 || res.processed.length === 0) break;
      }
      await qc.invalidateQueries({ queryKey: ["graph"] });
      if (failed) toast.warning(`${failed} document(s) could not be processed`);
      else toast.success("Knowledge graph updated");
    } catch (err: unknown) {
      toast.error("Graph extraction failed", {
        description: err instanceof Error ? err.message : undefined,
      });
    } finally {
      setBuilding(false);
    }
  }

  const g = graph.data;
  const types = useMemo(() => Array.from(new Set(g?.nodes.map((n) => n.type) ?? [])).sort(), [g]);
  const visibleNodes = (g?.nodes ?? []).filter(
    (n) =>
      (typeFilter === "ALL" || n.type === typeFilter) &&
      n.name.toLowerCase().includes(search.trim().toLowerCase()),
  );
  const pendingDocs = g ? g.documents_in_scope - g.documents_extracted : 0;
  const usedPattern = g?.extractions.some((e) => e.method === "pattern");

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          trigger ?? (
            <button type="button" className="tool-button">
              <Network className="size-3.5" aria-hidden />
              Graph
            </button>
          )
        }
      />
      <DialogContent className="flex max-h-[90vh] flex-col overflow-hidden p-6 sm:max-w-5xl">
        <DialogHeader className="shrink-0">
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Network className="size-5 text-primary" aria-hidden />
            Knowledge graph
          </DialogTitle>
          <DialogDescription className="text-xs">
            People, organizations, places and concepts named in your documents, and the
            relationships the text states. Every fact links back to its passage.
          </DialogDescription>
        </DialogHeader>

        <div className="my-2 flex-1 space-y-4 overflow-y-auto pr-1">
          <details className="rounded-lg border border-border bg-card p-3">
            <summary className="cursor-pointer select-none text-xs font-medium">
              Scope{selectedDocs.length ? ` · ${selectedDocs.length} selected` : " · all documents in scope"}
            </summary>
            <div className="mt-3">
              <ScopePicker selected={selectedDocs} onChange={(s) => { setSelectedDocs(s); setSelected(null); }} />
            </div>
          </details>

          {graph.isPending ? (
            <Skeleton className="h-64 w-full rounded-lg" />
          ) : graph.isError ? (
            <InlineError message={graph.error.message} onRetry={() => graph.refetch()} />
          ) : g ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                <span role="status">
                  {g.documents_extracted}/{g.documents_in_scope} documents processed · {g.total_entities} entities ·{" "}
                  {g.edges.length} relationships shown
                  {g.truncated && ` · showing the ${g.nodes.length} most-mentioned entities`}
                </span>
                <div className="flex gap-1.5">
                  {pendingDocs > 0 && (
                    <button type="button" onClick={() => build(false)} disabled={building} className="primary-button h-8">
                      {building ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Network className="size-3.5" aria-hidden />}
                      {building ? "Extracting…" : `Process ${pendingDocs} document${pendingDocs === 1 ? "" : "s"}`}
                    </button>
                  )}
                  {g.documents_extracted > 0 && (
                    <button type="button" onClick={() => build(true)} disabled={building} className="secondary-button">
                      <RefreshCw className={cn("size-3.5", building && "animate-spin")} aria-hidden />
                      Rebuild
                    </button>
                  )}
                </div>
              </div>

              {building && (
                <p role="status" aria-live="polite" className="text-xs text-muted-foreground">
                  Extracting entities with the local model, a few documents at a time. Large
                  scopes can take several minutes on CPU.
                </p>
              )}
              {usedPattern && (
                <p role="note" className="rounded-md border border-warning/30 bg-warning-soft px-3 py-2 text-xs text-warning">
                  Some documents were processed without the local model (it was unavailable):
                  their entities are capitalized names and their links only mean “mentioned
                  together”. Rebuild once Ollama is running for stated relationships.
                </p>
              )}

              {g.documents_in_scope === 0 ? (
                <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
                  No documents in this scope.
                </p>
              ) : g.nodes.length === 0 ? (
                <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
                  {g.documents_extracted === 0
                    ? "The graph hasn't been built for this scope yet. Process the documents to extract entities."
                    : "No entities were found in the processed documents."}
                </p>
              ) : (
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
                  <div className="space-y-2">
                    <GraphCanvas graph={g} selected={selected} onSelect={setSelected} />
                    <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
                      {types.map((t) => (
                        <span key={t} className="flex items-center gap-1">
                          <span className="size-2 rounded-full" style={{ background: TYPE_COLOR[t] ?? TYPE_COLOR.OTHER }} aria-hidden />
                          {t.toLowerCase()}
                        </span>
                      ))}
                      <span className="flex items-center gap-1">
                        <svg width="18" height="4" aria-hidden><line x1="0" y1="2" x2="18" y2="2" stroke="currentColor" /></svg>
                        supported
                      </span>
                      <span className="flex items-center gap-1">
                        <svg width="18" height="4" aria-hidden><line x1="0" y1="2" x2="18" y2="2" stroke="currentColor" strokeDasharray="4 3" /></svg>
                        uncertain
                      </span>
                    </div>
                  </div>

                  <aside aria-label="Entity details" className="min-w-0 rounded-lg border border-border bg-card p-3">
                    {selected ? (
                      <EntityDetails id={selected} scope={scope} onBack={() => setSelected(null)} onSelect={setSelected} />
                    ) : (
                      <div className="flex flex-col gap-2">
                        <div className="relative">
                          <Search className="pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
                          <Input
                            aria-label="Search entities"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            placeholder="Search entities"
                            className="pl-7"
                          />
                        </div>
                        <select
                          aria-label="Filter by type"
                          value={typeFilter}
                          onChange={(e) => setTypeFilter(e.target.value)}
                          className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                        >
                          <option value="ALL">All types</option>
                          {types.map((t) => (
                            <option key={t} value={t}>{t.toLowerCase()}</option>
                          ))}
                        </select>
                        <ul className="flex max-h-72 flex-col gap-0.5 overflow-y-auto" aria-label="Entities">
                          {visibleNodes.map((n) => (
                            <li key={n.id}>
                              <button
                                type="button"
                                onClick={() => setSelected(n.id)}
                                className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-xs hover:bg-accent"
                              >
                                <span className="size-2 shrink-0 rounded-full" style={{ background: TYPE_COLOR[n.type] ?? TYPE_COLOR.OTHER }} aria-hidden />
                                <span className="min-w-0 flex-1 truncate">{n.name}</span>
                                <span className="tabular-nums text-muted-foreground">{n.mentions}</span>
                              </button>
                            </li>
                          ))}
                          {visibleNodes.length === 0 && (
                            <li className="px-2 py-1 text-xs text-muted-foreground">No matching entities.</li>
                          )}
                        </ul>
                        {g.possible_duplicates.length > 0 && (
                          <details className="text-xs">
                            <summary className="cursor-pointer text-muted-foreground">
                              {g.possible_duplicates.length} possible duplicate{g.possible_duplicates.length === 1 ? "" : "s"} (not merged)
                            </summary>
                            <ul className="mt-1 space-y-1">
                              {g.possible_duplicates.map((d) => (
                                <li key={`${d.a}-${d.b}`} className="text-muted-foreground">
                                  “{d.a_name}” / “{d.b_name}” — {d.reason.toLowerCase()}
                                </li>
                              ))}
                            </ul>
                          </details>
                        )}
                      </div>
                    )}
                  </aside>
                </div>
              )}

              {g.extractions.some((e) => e.status === "failed") && (
                <p className="text-xs text-error">
                  Failed: {g.extractions.filter((e) => e.status === "failed").map((e) => e.filename).join(", ")}
                </p>
              )}
            </>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
