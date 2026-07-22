"use client";

// Model details — replaces the old toast (which vanished on its own
// and couldn't be re-consulted) with a proper dialog, matching the
// Document Library's pattern: press the row, get a persistent view
// you can reopen any time GET /status is unreachable to check again.

import { Settings } from "lucide-react";

import { InlineError } from "@/components/shared/inline-error";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useStatus } from "@/hooks/useStatus";

export function ModelDetailsDialog() {
  const status = useStatus();
  const s = status.data;

  const rows = s
    ? [
        { label: "LLM model", value: s.llm_model },
        { label: "Embedding model", value: s.embedding_model },
        { label: "Chunk size", value: `${s.chunk_size} chars` },
        { label: "Chunk overlap", value: `${s.chunk_overlap} chars` },
        { label: "Chunks retrieved (Top-K)", value: String(s.top_k) },
      ]
    : [];

  return (
    <Dialog>
      {/* Base UI composition: `render` supplies the element, children
          render inside it — same pattern as the other sidebar triggers. */}
      <DialogTrigger
        render={
          <button
            type="button"
            className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-[13px] transition-colors duration-150 hover:bg-sidebar-accent"
          />
        }
      >
        <span className="flex items-center gap-2">
          <Settings className="size-4 text-muted-foreground" aria-hidden />
          Model details
        </span>
      </DialogTrigger>

      <DialogContent className="max-w-[calc(100%-2rem)] sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Model Details</DialogTitle>
          <DialogDescription>
            The embedding and language models configured for this knowledge
            base.
          </DialogDescription>
        </DialogHeader>

        {status.isError ? (
          <InlineError
            message="Couldn't load model details"
            onRetry={() => status.refetch()}
          />
        ) : (
          <dl className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
            {rows.map((row) => (
              <div
                key={row.label}
                className="flex items-baseline justify-between gap-3"
              >
                <dt className="text-[13px] text-muted-foreground">
                  {row.label}
                </dt>
                <dd className="font-mono text-[13px] font-medium">
                  {row.value}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </DialogContent>
    </Dialog>
  );
}
