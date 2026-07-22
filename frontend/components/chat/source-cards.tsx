"use client";

// Source citation cards — rendered under each assistant answer.
// Collapsed to a quiet "Sources · N" disclosure by default
// (DESIGN.md §11); expanding lists one row per cited chunk with
// filename, chunk number, and similarity score. Rows that carry a
// preview snippet expand again to show it — two levels, both
// keyboard-operable buttons.

import { ChevronDown, Link2 } from "lucide-react";
import { useState } from "react";

import { CopyButton } from "@/components/shared/copy-button";
import { SimilarityBadge } from "@/components/shared/similarity-badge";
import type { Source } from "@/lib/types";

/** "zephyra.txt-3" -> "3" (filenames may themselves contain dashes). */
function chunkNumber(chunkId: string): string {
  return chunkId.slice(chunkId.lastIndexOf("-") + 1);
}

function SourceRow({ source }: { source: Source }) {
  const [open, setOpen] = useState(false);
  const expandable = Boolean(source.preview);

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

      {open && source.preview && (
        <div className="flex items-start justify-between gap-2 border-t border-border px-3 py-2">
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
    </li>
  );
}

export function SourceCards({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState(false);

  if (sources.length === 0) return null;

  return (
    <div className="mt-3 border-t border-border pt-2">
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

      {open && (
        <ul className="mt-2 flex flex-col gap-1.5">
          {sources.map((source) => (
            <SourceRow key={source.chunk_id} source={source} />
          ))}
        </ul>
      )}
    </div>
  );
}
