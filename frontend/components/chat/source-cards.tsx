"use client";

// Source citation cards — rendered under each assistant answer.
// Collapsed to a quiet "Sources · N" disclosure by default
// (DESIGN.md §11); expanding lists one row per cited chunk with
// filename, chunk number, similarity score, and citation verification status.

import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  HelpCircle,
  Link2,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useState } from "react";

import { CopyButton } from "@/components/shared/copy-button";
import { SimilarityBadge } from "@/components/shared/similarity-badge";
import type { Source, VerificationItem } from "@/lib/types";

/** "zephyra.txt-3" -> "3" (filenames may themselves contain dashes). */
function chunkNumber(chunkId: string): string {
  return chunkId.slice(chunkId.lastIndexOf("-") + 1);
}

function StatusBadge({ status }: { status: VerificationItem["status"] }) {
  switch (status) {
    case "SUPPORTED":
      return (
        <span className="inline-flex items-center gap-1 shrink-0 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 font-medium text-xs text-emerald-600 dark:text-emerald-400">
          <CheckCircle2 className="size-3" aria-hidden />
          Supported
        </span>
      );
    case "PARTIALLY_SUPPORTED":
      return (
        <span className="inline-flex items-center gap-1 shrink-0 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-medium text-xs text-amber-600 dark:text-amber-400">
          <AlertTriangle className="size-3" aria-hidden />
          Partially supported
        </span>
      );
    case "UNSUPPORTED":
      return (
        <span className="inline-flex items-center gap-1 shrink-0 rounded-full border border-red-500/30 bg-red-500/10 px-2 py-0.5 font-medium text-xs text-red-600 dark:text-red-400">
          <XCircle className="size-3" aria-hidden />
          Unsupported
        </span>
      );
    case "UNVERIFIABLE":
    default:
      return (
        <span className="inline-flex items-center gap-1 shrink-0 rounded-full border border-slate-500/30 bg-slate-500/10 px-2 py-0.5 font-medium text-xs text-slate-600 dark:text-slate-400">
          <HelpCircle className="size-3" aria-hidden />
          Unverifiable
        </span>
      );
  }
}

function SourceRow({
  source,
  verifications = [],
}: {
  source: Source;
  verifications?: VerificationItem[];
}) {
  const [open, setOpen] = useState(false);
  const sourceVerifications = verifications.filter((v) =>
    v.citation_ids?.includes(source.chunk_id)
  );
  const expandable = Boolean(source.preview) || sourceVerifications.length > 0;

  return (
    <li className="rounded-md border border-border bg-background">
      <button
        type="button"
        disabled={!expandable}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={expandable ? open : undefined}
        title={source.chunk_id}
        className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left transition-colors duration-150 enabled:hover:bg-accent disabled:cursor-default"
      >
        <span className="min-w-0 flex-1 truncate text-[13px] font-semibold">
          {source.filename}
        </span>
        <span className="shrink-0 rounded-full bg-secondary px-2 py-0.5 font-mono text-xs text-muted-foreground">
          chunk {chunkNumber(source.chunk_id)}
        </span>
        {source.page !== undefined && source.page !== null && (
          <span className="shrink-0 rounded-full bg-secondary px-2 py-0.5 font-mono text-xs text-muted-foreground">
            page {source.page}
          </span>
        )}
        {sourceVerifications.length > 0 && (
          <StatusBadge status={sourceVerifications[0].status} />
        )}
        <SimilarityBadge score={source.similarity} />
        {expandable && (
          <ChevronDown
            className={`size-3.5 shrink-0 text-muted-foreground transition-transform duration-150 ${
              open ? "rotate-180" : ""
            }`}
            aria-hidden
          />
        )}
      </button>

      {open && (
        <div className="flex flex-col gap-2 border-t border-border px-3 py-2">
          {sourceVerifications.length > 0 && (
            <div className="flex flex-col gap-1.5 pb-1">
              <span className="text-xs font-semibold text-foreground">
                Evidence Verification:
              </span>
              {sourceVerifications.map((v, i) => (
                <div
                  key={i}
                  className="rounded border border-border bg-secondary/40 p-2 text-xs"
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="font-medium text-foreground">
                      &quot;{v.claim}&quot;
                    </span>
                    <StatusBadge status={v.status} />
                  </div>
                  <p className="text-muted-foreground leading-relaxed">
                    {v.reason}
                  </p>
                </div>
              ))}
            </div>
          )}

          {source.preview && (
            <div className="flex items-start justify-between gap-2 border-t border-border/50 pt-2">
              <p className="text-[13px] leading-relaxed text-muted-foreground">
                {source.preview}
              </p>
              <CopyButton
                text={source.preview}
                label="Copy source text"
                className="shrink-0 p-1"
              />
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export function SourceCards({
  sources,
  verifications = [],
}: {
  sources: Source[];
  verifications?: VerificationItem[];
}) {
  const [open, setOpen] = useState(false);
  const [showVerification, setShowVerification] = useState(false);

  if (sources.length === 0) return null;

  return (
    <div className="mt-3 border-t border-border pt-2 flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex items-center gap-1.5 rounded-sm px-1 py-0.5 text-xs font-medium text-muted-foreground transition-colors duration-150 hover:text-foreground"
        >
          <Link2 className="size-3.5" aria-hidden />
          Sources · {sources.length}
          <ChevronDown
            className={`size-3.5 transition-transform duration-150 ${
              open ? "rotate-180" : ""
            }`}
            aria-hidden
          />
        </button>

        {verifications.length > 0 && (
          <button
            type="button"
            onClick={() => setShowVerification((v) => !v)}
            aria-expanded={showVerification}
            className="flex items-center gap-1.5 rounded-sm px-1 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400 transition-colors duration-150 hover:underline"
          >
            <ShieldCheck className="size-3.5" aria-hidden />
            Verification ({verifications.length} claims)
          </button>
        )}
      </div>

      {showVerification && verifications.length > 0 && (
        <div className="rounded-md border border-border bg-card p-3 text-xs flex flex-col gap-2">
          <div className="font-semibold text-foreground flex items-center gap-1.5">
            <ShieldCheck className="size-4 text-emerald-500" />
            Claim Verification Results
          </div>
          <div className="flex flex-col gap-2">
            {verifications.map((v, idx) => (
              <div
                key={idx}
                className="rounded border border-border bg-secondary/30 p-2.5 flex flex-col gap-1"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium text-foreground text-[12.5px]">
                    &quot;{v.claim}&quot;
                  </span>
                  <StatusBadge status={v.status} />
                </div>
                <p className="text-muted-foreground text-xs leading-relaxed">
                  {v.reason}
                </p>
                {v.citation_ids && v.citation_ids.length > 0 && (
                  <div className="flex items-center gap-1 text-[11px] text-muted-foreground mt-0.5">
                    <span>Cited sources:</span>
                    <span className="font-mono">
                      {v.citation_ids.join(", ")}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {open && (
        <ul className="mt-1 flex flex-col gap-1.5">
          {sources.map((source) => (
            <SourceRow
              key={source.chunk_id}
              source={source}
              verifications={verifications}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
