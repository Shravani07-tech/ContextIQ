"use client";

// Evidence assessment views (C8). One claim card used both under chat
// answers and in the claim-check dialog. Ratings are categorical on
// purpose — the backend never produces a percentage, so the UI never
// implies one — and every card says *why* via the factor list and the
// explanation lines, with the passages it relied on.

import { ChevronDown, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { SourceLocator } from "@/components/insights/source-locator";
import { ToneBadge, type Tone } from "@/components/insights/tone-badge";
import type { ClaimAssessment, EvidenceAssessment, EvidenceRating } from "@/lib/types";
import { cn } from "@/lib/utils";

export const RATING: Record<EvidenceRating, { tone: Tone; label: string; help: string }> = {
  STRONG: { tone: "success", label: "Strong", help: "Directly supported by two or more independent sources, with no detected conflict." },
  MODERATE: { tone: "success", label: "Moderate", help: "Directly supported by one independent source." },
  LIMITED: { tone: "info", label: "Limited", help: "Partly supported, or only keyword overlap was found." },
  CONTESTED: { tone: "error", label: "Contested", help: "Sources conflict on this claim." },
  UNSUPPORTED: { tone: "error", label: "Unsupported", help: "The retrieved passages do not support this claim." },
  INSUFFICIENT: { tone: "neutral", label: "Insufficient", help: "Not enough relevant evidence was retrieved to judge." },
};

const DIRECTNESS: Record<string, string> = {
  DIRECT: "direct",
  PARTIAL: "partial",
  NONE: "not supported",
  UNKNOWN: "undetermined",
  NOT_ASSESSED: "not model-checked",
};

export function RatingBadge({ rating }: { rating: EvidenceRating }) {
  const r = RATING[rating] ?? RATING.INSUFFICIENT;
  return (
    <ToneBadge tone={r.tone} title={r.help}>
      {r.label}
    </ToneBadge>
  );
}

export function ClaimCard({ item, defaultOpen = false }: { item: ClaimAssessment; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const f = item.factors;
  return (
    <li className="rounded-md border border-border bg-background">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-start gap-2 rounded-md px-3 py-2 text-left hover:bg-accent"
      >
        <RatingBadge rating={item.rating} />
        <span className="min-w-0 flex-1 text-[13px] leading-snug">{item.claim}</span>
        <ChevronDown
          className={cn("mt-0.5 size-3.5 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")}
          aria-hidden
        />
      </button>
      {open && (
        <div className="flex flex-col gap-2 border-t border-border px-3 py-2 text-xs">
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 sm:grid-cols-4">
            <div>
              <dt className="text-muted-foreground">Support</dt>
              <dd>{DIRECTNESS[f.directness] ?? f.directness.toLowerCase()}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Independent sources</dt>
              <dd className="tabular-nums">
                {f.independent_sources}
                {f.duplicates_collapsed > 0 && ` (+${f.duplicates_collapsed} duplicate)`}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Relevance</dt>
              <dd>{f.relevance.toLowerCase()}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Conflict</dt>
              <dd>{f.contradiction === "NONE" ? "none detected" : f.contradiction.toLowerCase()}</dd>
            </div>
          </dl>
          <ul className="list-disc space-y-0.5 pl-4 text-muted-foreground">
            {item.explanation.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
          {item.passages.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <span className="font-medium">Passages considered</span>
              {item.passages.map((p) => (
                <div key={p.chunk_id} className="flex items-start gap-2">
                  <ToneBadge tone="neutral" title="Keyword overlap with the claim">
                    {p.relevance.toLowerCase()}
                    {p.cited_by_check ? " · cited" : ""}
                  </ToneBadge>
                  <SourceLocator source={p} className="flex-1" />
                </div>
              ))}
            </div>
          )}
          <p className="text-[11px] text-muted-foreground/80">
            Basis: {item.basis === "heuristic" ? "keyword overlap only (model check unavailable)" : "model-assisted citation check + rules"}
          </p>
        </div>
      )}
    </li>
  );
}

export function EvidencePanel({ assessment }: { assessment?: EvidenceAssessment | null }) {
  const [open, setOpen] = useState(false);
  if (!assessment || assessment.claims.length === 0) return null;
  const order: EvidenceRating[] = ["STRONG", "MODERATE", "LIMITED", "CONTESTED", "UNSUPPORTED", "INSUFFICIENT"];

  return (
    <div className="mt-3 flex flex-col gap-2 border-t border-border pt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex flex-wrap items-center gap-1.5 rounded-sm px-1 py-0.5 text-left text-xs font-semibold text-muted-foreground hover:text-foreground"
      >
        <ShieldCheck className="size-3.5" aria-hidden />
        Evidence assessment
        <span className="flex flex-wrap gap-1 font-normal">
          {order
            .filter((r) => assessment.counts[r])
            .map((r) => (
              <ToneBadge key={r} tone={RATING[r].tone}>
                {assessment.counts[r]} {RATING[r].label.toLowerCase()}
              </ToneBadge>
            ))}
        </span>
        <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <>
          <p className="px-1 text-xs">{assessment.overall}</p>
          <ul className="flex flex-col gap-1.5">
            {assessment.claims.map((c) => (
              <ClaimCard key={c.claim} item={c} />
            ))}
          </ul>
          <p className="px-1 text-[11px] text-muted-foreground/80">{assessment.disclaimer}</p>
        </>
      )}
    </div>
  );
}
