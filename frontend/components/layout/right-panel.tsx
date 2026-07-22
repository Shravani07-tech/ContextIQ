"use client";

// Right utility panel — fully live:
//   Recent Sources        <- the latest assistant answer's citations
//   Knowledge Statistics  <- GET /status (vectors, docs, chunking, top-K)
//   System Status         <- GET /health (API / ChromaDB / Ollama)

import { Activity, BarChart3, Link2, SearchX } from "lucide-react";

import { EmptyPanelState } from "@/components/shared/empty-panel-state";
import { SimilarityBadge } from "@/components/shared/similarity-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useChat } from "@/hooks/useChat";
import { useHealth } from "@/hooks/useHealth";
import { useStatus } from "@/hooks/useStatus";

function PanelSection({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.06em] text-muted-foreground">
        {icon}
        {title}
      </p>
      {children}
    </section>
  );
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`flex items-center gap-1.5 text-xs ${ok ? "text-success" : "text-error"}`}
    >
      <span
        className={`size-1.5 rounded-full ${ok ? "bg-success" : "bg-error"}`}
        aria-hidden
      />
      {ok ? "ok" : "down"}
    </span>
  );
}

export function RightPanel() {
  const { lastSources } = useChat();
  const status = useStatus();
  const health = useHealth();

  // Every value live from GET /status; em dash only while loading
  // or unreachable — never a fake number.
  const s = status.data;
  const stats = [
    { label: "Documents", value: s ? String(s.document_count) : "—" },
    { label: "Vectors", value: s ? String(s.vector_count) : "—" },
    {
      label: "Chunk size",
      value: s ? `${s.chunk_size} / ${s.chunk_overlap}` : "—",
    },
    { label: "Top-K", value: s ? String(s.top_k) : "—" },
  ];

  const systems = [
    { label: "API", ok: health.isSuccess },
    { label: "ChromaDB", ok: health.data?.chroma ?? false },
    { label: "Ollama", ok: health.data?.ollama ?? false },
  ];

  return (
    <aside className="flex h-full w-72 flex-col gap-6 overflow-y-auto border-l border-border bg-background p-4">
      <PanelSection
        icon={<Link2 className="size-3.5" aria-hidden />}
        title="Recent Sources"
      >
        {lastSources.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {/* Named `source`, not `s` — avoids shadowing the outer
                `s` (status.data) bound just above this block. */}
            {lastSources.map((source) => (
              <li
                key={source.chunk_id}
                className="rounded-md border border-border bg-card p-3 transition-colors duration-150 hover:bg-accent"
              >
                <p className="truncate text-[13px] font-semibold">
                  {source.filename}
                </p>
                <div className="mt-1 flex items-center justify-between gap-2">
                  <span className="truncate rounded-full bg-secondary px-2 py-0.5 font-mono text-xs text-muted-foreground">
                    {source.chunk_id}
                  </span>
                  <SimilarityBadge score={source.similarity} />
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyPanelState
            icon={SearchX}
            title="No sources yet"
            description="Cited chunks appear after your first question"
          />
        )}
      </PanelSection>

      <PanelSection
        icon={<BarChart3 className="size-3.5" aria-hidden />}
        title="Knowledge Statistics"
      >
        {status.isPending ? (
          <Skeleton className="h-28 rounded-lg" />
        ) : (
          <div className="rounded-lg border border-border bg-card p-4">
            <dl className="flex flex-col gap-2">
              {stats.map((stat) => (
                <div
                  key={stat.label}
                  className="flex items-baseline justify-between gap-2"
                >
                  <dt className="text-[13px] text-muted-foreground">
                    {stat.label}
                  </dt>
                  <dd className="font-mono text-[13px] font-medium tabular-nums">
                    {stat.value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )}
      </PanelSection>

      <PanelSection
        icon={<Activity className="size-3.5" aria-hidden />}
        title="System Status"
      >
        <ul className="flex flex-col gap-1">
          {systems.map((sys) => (
            <li
              key={sys.label}
              className="flex items-center justify-between rounded-md px-2 py-1.5 text-[13px] transition-colors duration-150 hover:bg-accent"
            >
              <span>{sys.label}</span>
              <StatusDot ok={sys.ok} />
            </li>
          ))}
        </ul>
      </PanelSection>
    </aside>
  );
}
