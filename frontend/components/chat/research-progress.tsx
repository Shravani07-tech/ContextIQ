"use client";

// Deep research (C11) progress and result views.
//
// ResearchProgress renders the live step list while a bounded research
// run is in flight, so the user sees what the system is doing (planning,
// each search and how much it found, follow-ups, synthesis, checks)
// instead of an unexplained spinner. ResearchPanel renders the finished
// run: each sub-question's status, what remains unresolved, warnings,
// and the limits that bounded the run.
//
// Sub-question statuses describe the EVIDENCE, not the answer's
// content: "Evidence found" means relevant passages were retrieved and
// cited — the passages may still lack the specific fact asked for.

import { CheckCircle2, ChevronDown, CircleDashed, CircleHelp, Loader2, Telescope } from "lucide-react";
import { useState } from "react";

import { ToneBadge, type Tone } from "@/components/insights/tone-badge";
import type { ChatMessage, ResearchStep, ResearchSubquestion } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ResearchProgress({ steps }: { steps: ResearchStep[] }) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Research progress"
      className="rounded-lg border border-border bg-card px-4 py-3"
    >
      <p className="mb-2 flex items-center gap-2 text-xs font-semibold">
        <Telescope className="size-3.5 text-primary" aria-hidden />
        Deep research in progress
      </p>
      <ol className="flex flex-col gap-1 text-xs">
        {steps.map((s, i) => {
          const last = i === steps.length - 1;
          return (
            <li key={`${s.stage}-${i}`} className={cn("flex items-start gap-2", !last && "text-muted-foreground")}>
              {last ? (
                <Loader2 className="mt-0.5 size-3 shrink-0 animate-spin text-primary" aria-hidden />
              ) : (
                <CheckCircle2 className="mt-0.5 size-3 shrink-0 text-success" aria-hidden />
              )}
              <span>
                {s.message}
                {typeof s.found === "number" && (
                  <span className="text-muted-foreground"> — {s.found} passage{s.found === 1 ? "" : "s"}</span>
                )}
              </span>
            </li>
          );
        })}
        {steps.length === 0 && (
          <li className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="size-3 animate-spin" aria-hidden /> Starting…
          </li>
        )}
      </ol>
    </div>
  );
}

const SUB_STATUS: Record<ResearchSubquestion["status"], { tone: Tone; label: string; icon: typeof CheckCircle2 }> = {
  ANSWERED: { tone: "success", label: "Evidence found", icon: CheckCircle2 },
  PARTIAL: { tone: "warning", label: "Weak evidence", icon: CircleDashed },
  UNRESOLVED: { tone: "error", label: "No evidence", icon: CircleHelp },
};

const RUN_STATUS: Record<string, Tone> = {
  COMPLETED: "success",
  PARTIAL: "warning",
  CANCELLED: "neutral",
  FAILED: "error",
};

export function ResearchPanel({ research }: { research: NonNullable<ChatMessage["research"]> }) {
  const [open, setOpen] = useState(research.status !== "COMPLETED");
  const limits = research.limits ?? {};

  return (
    <div className="mt-3 flex flex-col gap-2 border-t border-border pt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex flex-wrap items-center gap-1.5 rounded-sm px-1 py-0.5 text-left text-xs font-semibold text-muted-foreground hover:text-foreground"
      >
        <Telescope className="size-3.5" aria-hidden />
        Research process
        <ToneBadge tone={RUN_STATUS[research.status] ?? "neutral"}>{research.status.toLowerCase()}</ToneBadge>
        <span className="font-normal">
          {research.subquestions.length} sub-question{research.subquestions.length === 1 ? "" : "s"} ·{" "}
          {limits.retrievals_used ?? 0}/{limits.max_retrievals ?? "?"} searches
        </span>
        <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} aria-hidden />
      </button>

      {open && (
        <div className="flex flex-col gap-2 text-xs">
          <ul className="flex flex-col gap-1.5">
            {research.subquestions.map((sq) => {
              const st = SUB_STATUS[sq.status] ?? SUB_STATUS.UNRESOLVED;
              return (
                <li key={sq.question} className="rounded-md border border-border bg-background px-3 py-2">
                  <div className="flex items-start gap-2">
                    <ToneBadge tone={st.tone}>
                      <st.icon className="size-3" aria-hidden />
                      {st.label}
                    </ToneBadge>
                    <span className="min-w-0 flex-1">{sq.question}</span>
                  </div>
                  <p className="mt-1 text-muted-foreground">
                    {sq.source_labels.length > 0 ? `Evidence: ${sq.source_labels.join(", ")}` : "No evidence used"}
                    {sq.queries.length > 1 && ` · ${sq.queries.length} searches`}
                    {sq.note && ` · ${sq.note}`}
                  </p>
                </li>
              );
            })}
          </ul>
          {research.unresolved.length > 0 && (
            <p className="rounded-md border border-warning/30 bg-warning-soft px-3 py-2 text-warning">
              Little or no supporting evidence in your documents for: {research.unresolved.join(" · ")}
            </p>
          )}
          {research.warnings.map((w) => (
            <p key={w} role="note" className="text-muted-foreground">
              {w}
            </p>
          ))}
          <p className="text-[11px] text-muted-foreground/80">
            Scope: {research.scope} · planning: {research.plan_method} · follow-up searches:{" "}
            {limits.followups_used ?? 0}/{limits.max_followups ?? "?"} · {limits.elapsed_seconds ?? "?"}s
          </p>
        </div>
      )}
    </div>
  );
}
