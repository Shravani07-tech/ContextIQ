"use client";

// Contradiction Cards — rendered under assistant answers when evidence conflicts.
// Displays conflicting statements side-by-side with source attribution and explanation.

import { AlertOctagon, AlertTriangle, ChevronDown } from "lucide-react";
import { useState } from "react";

import type { ContradictionItem } from "@/lib/types";

export function ContradictionCards({
  contradictions,
}: {
  contradictions?: ContradictionItem[];
}) {
  const [open, setOpen] = useState(true);

  if (!contradictions || contradictions.length === 0) return null;

  return (
    <div className="mt-3 border-t border-amber-500/20 pt-2 flex flex-col gap-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-sm px-1 py-0.5 text-xs font-semibold text-amber-600 dark:text-amber-400 transition-colors duration-150 hover:underline"
      >
        <AlertTriangle className="size-3.5 text-amber-500" aria-hidden />
        Contradictions Detected ({contradictions.length})
        <ChevronDown
          className={`size-3.5 transition-transform duration-150 ${
            open ? "rotate-180" : ""
          }`}
          aria-hidden
        />
      </button>

      {open && (
        <div className="flex flex-col gap-2">
          {contradictions.map((item, idx) => {
            const isHigh = item.severity === "HIGH" || item.status === "CONTRADICTION";
            return (
              <div
                key={idx}
                className={`rounded-md border p-3 text-xs flex flex-col gap-2 ${
                  isHigh
                    ? "border-red-500/30 bg-red-500/5"
                    : "border-amber-500/30 bg-amber-500/5"
                }`}
              >
                <div className="flex items-center justify-between gap-2 font-semibold">
                  <span className="flex items-center gap-1.5 text-foreground text-[12.5px]">
                    <AlertOctagon
                      className={`size-3.5 ${
                        isHigh ? "text-red-500" : "text-amber-500"
                      }`}
                    />
                    {item.topic}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 font-mono text-[10px] font-bold ${
                      isHigh
                        ? "bg-red-500/20 text-red-600 dark:text-red-400"
                        : "bg-amber-500/20 text-amber-600 dark:text-amber-400"
                    }`}
                  >
                    {item.status === "CONTRADICTION"
                      ? "CONTRADICTION"
                      : "POTENTIAL CONTRADICTION"}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 my-0.5">
                  <div className="rounded border border-border bg-background p-2 flex flex-col gap-1">
                    <span className="font-semibold text-muted-foreground text-[11px] truncate">
                      Source A ({item.source_a}):
                    </span>
                    <p className="text-foreground leading-relaxed">
                      &quot;{item.claim_a}&quot;
                    </p>
                  </div>

                  <div className="rounded border border-border bg-background p-2 flex flex-col gap-1">
                    <span className="font-semibold text-muted-foreground text-[11px] truncate">
                      Source B ({item.source_b}):
                    </span>
                    <p className="text-foreground leading-relaxed">
                      &quot;{item.claim_b}&quot;
                    </p>
                  </div>
                </div>

                <p className="text-muted-foreground text-xs leading-relaxed border-t border-border/50 pt-1.5">
                  <span className="font-semibold text-foreground">Reason: </span>
                  {item.reason}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
