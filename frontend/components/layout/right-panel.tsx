"use client";

// Right utility panel — now live:
//   Recent Sources        <- the latest assistant answer's citations
//   Knowledge Statistics  <- document count from GET /documents
//   System Status         <- GET /health (API / ChromaDB / Ollama)
// Vector count, chunk size, and top-K need GET /status — wired in
// Phase 3B; until then those rows show an em dash, not fake numbers.

import { Activity, BarChart3, Link2, SearchX } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { useChat } from "@/hooks/useChat";
import { useDocuments } from "@/hooks/useDocuments";
import { useHealth } from "@/hooks/useHealth";

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
  const documents = useDocuments();
  const health = useHealth();

  const stats = [
    {
      label: "Documents",
      value: documents.isSuccess ? String(documents.data.length) : "—",
    },
    // These three come from GET /status — Phase 3B.
    { label: "Vectors", value: "—" },
    { label: "Chunk size", value: "—" },
    { label: "Top-K", value: "—" },
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
            {lastSources.map((s) => (
              <li
                key={s.chunk_id}
                className="rounded-md border border-border bg-card p-3 transition-colors duration-150 hover:bg-accent"
              >
                <p className="truncate text-[13px] font-semibold">
                  {s.filename}
                </p>
                <div className="mt-1 flex items-center justify-between gap-2">
                  <span className="truncate rounded-full bg-secondary px-2 py-0.5 font-mono text-xs text-muted-foreground">
                    {s.chunk_id}
                  </span>
                  <span className="shrink-0 text-[13px] font-bold tabular-nums text-ring">
                    {(s.similarity * 100).toFixed(1)}%
                  </span>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="flex flex-col items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-5 text-center">
            <SearchX className="size-4 text-muted-foreground" aria-hidden />
            <p className="text-[13px] text-muted-foreground">No sources yet</p>
            <p className="text-xs text-muted-foreground/70">
              Cited chunks appear after your first question
            </p>
          </div>
        )}
      </PanelSection>

      <PanelSection
        icon={<BarChart3 className="size-3.5" aria-hidden />}
        title="Knowledge Statistics"
      >
        {documents.isPending ? (
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
