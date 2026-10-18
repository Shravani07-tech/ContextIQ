"use client";

// Source locator — one consistent way to show where a timeline event,
// evidence passage, or graph fact came from: document name plus the most
// specific locator the parser recorded (page, slide, sheet, section).
// Every value comes from the backend's stored chunk metadata, so the UI
// never displays a locator that doesn't exist.

import { ChevronDown, FileText } from "lucide-react";
import { useState } from "react";

import type { SourceRef } from "@/lib/types";
import { cn } from "@/lib/utils";

export function formatLocator(source: Pick<SourceRef, "page" | "slide" | "sheet" | "section">): string {
  const parts: string[] = [];
  if (source.page) parts.push(`p. ${source.page}`);
  if (source.slide) parts.push(`slide ${source.slide}`);
  if (source.sheet) parts.push(`sheet ${source.sheet}`);
  if (source.section) parts.push(`§ ${source.section}`);
  return parts.join(" · ");
}

export function SourceLocator({
  source,
  className,
  showPreview = true,
}: {
  source: SourceRef;
  className?: string;
  showPreview?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const locator = formatLocator(source);
  const canExpand = showPreview && Boolean(source.preview);

  return (
    <div className={cn("flex min-w-0 flex-col gap-1", className)}>
      <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
        <span className="flex min-w-0 items-center gap-1 font-medium text-foreground/90">
          <FileText className="size-3 shrink-0" aria-hidden />
          <span className="truncate" title={source.filename}>
            {source.filename}
          </span>
        </span>
        {locator && <span className="truncate">{locator}</span>}
        {canExpand && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="flex items-center gap-0.5 rounded-sm px-1 text-xs text-primary hover:underline"
          >
            {open ? "Hide passage" : "View passage"}
            <ChevronDown
              className={cn("size-3 transition-transform", open && "rotate-180")}
              aria-hidden
            />
          </button>
        )}
      </div>
      {canExpand && open && (
        <blockquote className="rounded-md border-l-2 border-primary/40 bg-muted px-3 py-2 text-xs leading-relaxed text-muted-foreground">
          {source.preview}
        </blockquote>
      )}
    </div>
  );
}
