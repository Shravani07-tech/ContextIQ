"use client";

// Claim check dialog (C8): paste a statement, get a transparent rating
// of how well the documents in scope support it — with the factors,
// reasons, and passages behind the rating.

import { Loader2, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { ClaimCard } from "@/components/insights/evidence-view";
import { ScopePicker } from "@/components/insights/scope-picker";
import { InlineError } from "@/components/shared/inline-error";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useActiveCollection } from "@/hooks/useCollections";
import { api } from "@/lib/api";
import type { EvidenceAssessResponse } from "@/lib/types";

export function EvidenceDialog({ trigger }: { trigger?: React.ReactElement }) {
  const [open, setOpen] = useState(false);
  const [activeCollectionId] = useActiveCollection();
  const [selected, setSelected] = useState<string[]>([]);
  const [claim, setClaim] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EvidenceAssessResponse | null>(null);

  async function run() {
    const text = claim.trim();
    if (!text || isLoading) return;
    setIsLoading(true);
    setError(null);
    try {
      setResult(
        await api.assessEvidence({
          claim: text,
          collection_id: activeCollectionId,
          filenames: selected.length ? selected : null,
        }),
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Evidence check failed.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          trigger ?? (
            <button type="button" className="tool-button">
              <ShieldCheck className="size-3.5" aria-hidden />
              Check a claim
            </button>
          )
        }
      />
      <DialogContent className="flex max-h-[88vh] flex-col overflow-hidden p-6 sm:max-w-2xl">
        <DialogHeader className="shrink-0">
          <DialogTitle className="flex items-center gap-2 text-lg">
            <ShieldCheck className="size-5 text-primary" aria-hidden />
            Check a claim
          </DialogTitle>
          <DialogDescription className="text-xs">
            See how well your documents support a statement, which passages bear on it,
            and whether any sources conflict.
          </DialogDescription>
        </DialogHeader>

        <div className="my-2 flex-1 space-y-4 overflow-y-auto pr-1">
          <div className="space-y-3 rounded-lg border border-border bg-card p-4">
            <ScopePicker selected={selected} onChange={setSelected} />
            <label htmlFor="claim-input" className="block text-xs font-medium">
              Statement to check
            </label>
            <textarea
              id="claim-input"
              value={claim}
              onChange={(e) => setClaim(e.target.value)}
              maxLength={1000}
              rows={3}
              placeholder="e.g. Revenue grew 25% in 2024."
              className="w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground"
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run();
              }}
            />
            <div className="flex items-center justify-between gap-2">
              <span className="text-[11px] text-muted-foreground">{claim.length}/1000 · Ctrl+Enter to check</span>
              <button
                type="button"
                onClick={run}
                disabled={isLoading || !claim.trim()}
                className="primary-button"
              >
                {isLoading ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <ShieldCheck className="size-3.5" aria-hidden />}
                {isLoading ? "Checking…" : "Check evidence"}
              </button>
            </div>
          </div>

          {isLoading && (
            <div role="status" aria-live="polite" className="space-y-2">
              <p className="text-xs text-muted-foreground">
                Retrieving passages in scope, then running the local citation and
                contradiction checks…
              </p>
              <Skeleton className="h-16 w-full rounded-lg" />
            </div>
          )}

          {error && !isLoading && <InlineError message={error} onRetry={run} />}

          {result && !isLoading && (
            <section aria-label="Evidence result" className="space-y-3">
              <p className="text-xs text-muted-foreground">Scope: {result.scope}</p>
              {result.warnings.map((w) => (
                <p key={w} role="note" className="rounded-md border border-warning/30 bg-warning-soft px-3 py-2 text-xs text-warning">
                  {w}
                </p>
              ))}
              <ul>
                <ClaimCard item={result.assessment} defaultOpen />
              </ul>
              <p className="text-[11px] text-muted-foreground/80">{result.disclaimer}</p>
            </section>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
