"use client";

// Timeline dialog (C7). Builds a chronological, source-linked timeline
// for the active collection or a selection within it. Dates are shown
// with their original wording and an explicit certainty; events without
// a usable date are listed separately instead of being forced into the
// chronology. Ingestion dates are labelled as such, never as events.

import { CalendarClock, Download, Loader2, RefreshCw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ScopePicker, useScopeLabel } from "@/components/insights/scope-picker";
import { SourceLocator } from "@/components/insights/source-locator";
import { ToneBadge, type Tone } from "@/components/insights/tone-badge";
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
import { downloadBlob } from "@/lib/download";
import type { DateCertainty, TimelineEvent, TimelineResponse } from "@/lib/types";

const CERTAINTY: Record<DateCertainty, { tone: Tone; label: string; help: string }> = {
  EXACT: { tone: "success", label: "Exact", help: "The source states this date explicitly." },
  APPROXIMATE: { tone: "info", label: "Approximate", help: "The source gives an approximate or bounded date." },
  AMBIGUOUS: { tone: "warning", label: "Ambiguous", help: "The wording allows more than one reading; only the year is used." },
  RELATIVE: { tone: "warning", label: "Relative", help: "Relative wording (e.g. 'last year') cannot be placed without an anchor date." },
  UNKNOWN: { tone: "neutral", label: "No date", help: "The source gives no usable date for this event." },
};

const DATE_TYPE_LABEL: Record<TimelineEvent["date_type"], string | null> = {
  EVENT: null,
  PUBLICATION: "Publication date",
  MODIFIED: "Revision date",
  OTHER: "Other date",
};

function EventItem({ event }: { event: TimelineEvent }) {
  const c = CERTAINTY[event.date.certainty] ?? CERTAINTY.UNKNOWN;
  const typeLabel = DATE_TYPE_LABEL[event.date_type];
  return (
    <li className="relative pl-6">
      <span
        aria-hidden
        className="absolute left-[5px] top-1.5 size-2.5 rounded-full border-2 border-background bg-primary ring-1 ring-primary/40"
      />
      <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-card p-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-[13px] font-semibold tabular-nums">
            {event.date.text || "Undated"}
          </span>
          <ToneBadge tone={c.tone} title={event.date.note ?? c.help}>
            {c.label}
          </ToneBadge>
          {typeLabel && <ToneBadge tone="neutral">{typeLabel}</ToneBadge>}
          {event.date.text && !event.date.in_source && (
            <ToneBadge tone="warning" title={event.date.note ?? undefined}>
              Not found in source
            </ToneBadge>
          )}
        </div>
        <p className="text-[13.5px] leading-relaxed">{event.description}</p>
        {event.actors.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Involved: {event.actors.join(", ")}
          </p>
        )}
        <SourceLocator source={event.source} />
      </div>
    </li>
  );
}

export function timelineToMarkdown(result: TimelineResponse): string {
  const line = (e: TimelineEvent) =>
    `- **${e.date.text || "Undated"}** (${e.date.certainty.toLowerCase()}${
      e.date_type !== "EVENT" ? `, ${e.date_type.toLowerCase()}` : ""
    }) — ${e.description} _[${e.source.filename}${e.source.page ? `, p. ${e.source.page}` : ""}]_`;
  const parts = [`Timeline for ${result.scope}${result.focus ? ` — focus: ${result.focus}` : ""}.`, ""];
  parts.push(...result.events.map(line));
  if (result.undated_events.length) {
    parts.push("", "Events without a usable date:", ...result.undated_events.map(line));
  }
  return parts.join("\n");
}

export function TimelineDialog({ trigger }: { trigger?: React.ReactElement }) {
  const [open, setOpen] = useState(false);
  const [activeCollectionId] = useActiveCollection();
  const scopeLabel = useScopeLabel();
  const [selected, setSelected] = useState<string[]>([]);
  const [focus, setFocus] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TimelineResponse | null>(null);

  async function run() {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.timeline({
        collection_id: activeCollectionId,
        filenames: selected.length ? selected : null,
        focus: focus.trim() || null,
      });
      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Timeline extraction failed.");
    } finally {
      setIsLoading(false);
    }
  }

  async function exportReport() {
    if (!result) return;
    setIsExporting(true);
    try {
      const blob = await api.exportResearchReport({
        format: "markdown",
        question: `Timeline${result.focus ? `: ${result.focus}` : ""}`,
        answer: timelineToMarkdown(result),
        sources: [],
        doc_count: result.documents_analyzed,
        collection_name: scopeLabel,
        timeline: [...result.events, ...result.undated_events],
      });
      downloadBlob(blob, "contextiq-timeline.md");
      toast.success("Timeline exported");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Export failed");
    } finally {
      setIsExporting(false);
    }
  }

  const total = result ? result.events.length + result.undated_events.length : 0;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          trigger ?? (
            <button type="button" className="tool-button">
              <CalendarClock className="size-3.5" aria-hidden />
              Timeline
            </button>
          )
        }
      />
      <DialogContent className="flex max-h-[88vh] flex-col overflow-hidden p-6 sm:max-w-3xl">
        <DialogHeader className="shrink-0">
          <DialogTitle className="flex items-center gap-2 text-lg">
            <CalendarClock className="size-5 text-primary" aria-hidden />
            Timeline
          </DialogTitle>
          <DialogDescription className="text-xs">
            Events and dates found in your documents, in order. Dates keep their
            original wording; uncertain dates are marked, and nothing is guessed.
          </DialogDescription>
        </DialogHeader>

        <div className="my-2 flex-1 space-y-4 overflow-y-auto pr-1">
          <div className="space-y-3 rounded-lg border border-border bg-card p-4">
            <ScopePicker selected={selected} onChange={setSelected} />
            <div className="flex flex-col gap-2 sm:flex-row">
              <label className="sr-only" htmlFor="timeline-focus">
                Optional focus
              </label>
              <Input
                id="timeline-focus"
                value={focus}
                onChange={(e) => setFocus(e.target.value)}
                placeholder="Optional focus, e.g. 'product launches' (leave empty to scan all dates)"
                maxLength={300}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !isLoading) run();
                }}
              />
              <button
                type="button"
                onClick={run}
                disabled={isLoading}
                className="primary-button shrink-0"
              >
                {isLoading ? (
                  <Loader2 className="size-3.5 animate-spin" aria-hidden />
                ) : result ? (
                  <RefreshCw className="size-3.5" aria-hidden />
                ) : (
                  <CalendarClock className="size-3.5" aria-hidden />
                )}
                {isLoading ? "Extracting…" : result ? "Rebuild" : "Build timeline"}
              </button>
            </div>
          </div>

          {isLoading && (
            <div className="space-y-3" role="status" aria-live="polite">
              <p className="text-xs text-muted-foreground">
                Reading date-bearing passages and extracting events with the local
                model. This can take a minute on CPU.
              </p>
              <Skeleton className="h-20 w-full rounded-lg" />
              <Skeleton className="h-20 w-full rounded-lg" />
            </div>
          )}

          {error && !isLoading && <InlineError message={error} onRetry={run} />}

          {result && !isLoading && (
            <section aria-label="Timeline results" className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                <span>
                  {total} event{total === 1 ? "" : "s"} from {result.documents_analyzed} document
                  {result.documents_analyzed === 1 ? "" : "s"} · {result.chunks_analyzed} passages read ·{" "}
                  {result.extraction_method === "pattern"
                    ? "pattern matching (model unavailable)"
                    : result.extraction_method === "llm"
                      ? "local model"
                      : "nothing to analyze"}
                </span>
                {total > 0 && (
                  <button
                    type="button"
                    onClick={exportReport}
                    disabled={isExporting}
                    className="secondary-button"
                  >
                    {isExporting ? (
                      <Loader2 className="size-3.5 animate-spin" aria-hidden />
                    ) : (
                      <Download className="size-3.5" aria-hidden />
                    )}
                    Export
                  </button>
                )}
              </div>

              {result.warnings.map((w) => (
                <p key={w} role="note" className="rounded-md border border-warning/30 bg-warning-soft px-3 py-2 text-xs text-warning">
                  {w}
                </p>
              ))}

              {total === 0 ? (
                <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
                  No dated events were found in this scope.
                </p>
              ) : (
                <>
                  {result.events.length > 0 && (
                    <ol className="relative flex flex-col gap-3 before:absolute before:left-[9px] before:top-2 before:bottom-2 before:w-px before:bg-border">
                      {result.events.map((e) => (
                        <EventItem key={e.id} event={e} />
                      ))}
                    </ol>
                  )}
                  {result.undated_events.length > 0 && (
                    <div className="space-y-2">
                      <h3 className="text-xs font-bold uppercase tracking-[0.06em] text-muted-foreground">
                        Not placed on the timeline ({result.undated_events.length})
                      </h3>
                      <ul className="flex flex-col gap-3">
                        {result.undated_events.map((e) => (
                          <EventItem key={e.id} event={e} />
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}

              {result.document_dates.length > 0 && (
                <details className="rounded-md border border-border px-3 py-2 text-xs text-muted-foreground">
                  <summary className="cursor-pointer select-none">
                    Indexing dates (when files were added to ContextIQ — not event dates)
                  </summary>
                  <ul className="mt-2 space-y-1">
                    {result.document_dates.map((d) => (
                      <li key={d.filename} className="flex justify-between gap-2">
                        <span className="truncate">{d.filename}</span>
                        <span className="font-mono tabular-nums">
                          {d.indexed_at ? new Date(d.indexed_at).toLocaleDateString() : "—"}
                        </span>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </section>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
