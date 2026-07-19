"use client";

// Sidebar — now fully live: document list from GET /documents,
// uploads through POST /upload + /index, clearing via
// DELETE /database (gated behind a confirmation toast). Loading
// renders skeleton rows; errors render a retry card — never a blank
// gap. Layout and styling are unchanged from Phase 2.

import {
  ChevronRight,
  Database,
  FileText,
  FolderOpen,
  Loader2,
  Settings,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { UploadDropzone } from "@/components/sidebar/upload-dropzone";
import { Skeleton } from "@/components/ui/skeleton";
import { useClearDatabase } from "@/hooks/useDatabase";
import { useDocuments } from "@/hooks/useDocuments";
import { useChat } from "@/hooks/useChat";

function SectionLabel({ children }: { children: React.ReactNode }) {
  // DESIGN.md §3 "label" step: 12px, +0.06em tracking, uppercase.
  return (
    <p className="text-xs font-bold uppercase tracking-[0.06em] text-muted-foreground">
      {children}
    </p>
  );
}

export function Sidebar() {
  const documents = useDocuments();
  const clearDb = useClearDatabase();
  const { addSystemMessage } = useChat();

  const files = documents.data ?? [];

  function confirmClear() {
    toast.warning("Clear the entire knowledge base?", {
      description: "Every vector is deleted. Files on disk are kept.",
      action: {
        label: "Clear",
        onClick: () =>
          clearDb.mutate(undefined, {
            onSuccess: () => addSystemMessage("Knowledge base cleared"),
          }),
      },
    });
  }

  return (
    <aside className="flex h-full w-[280px] flex-col gap-6 border-r border-sidebar-border bg-sidebar p-4">
      {/* Brand lockup — 34px primary mark, name, official tagline. */}
      <div className="flex items-start gap-3">
        <div className="flex size-[34px] shrink-0 items-center justify-center rounded-md bg-sidebar-primary text-[15px] font-extrabold text-sidebar-primary-foreground">
          C
        </div>
        <div className="min-w-0">
          <p className="text-[15px] font-bold leading-tight">ContextIQ</p>
          <p className="text-xs leading-tight text-muted-foreground">
            Private AI-Powered Document Intelligence
          </p>
        </div>
      </div>

      {/* Knowledge base — upload + indexed files. */}
      <div className="flex flex-col gap-3">
        <SectionLabel>Knowledge Base</SectionLabel>

        <UploadDropzone />

        {documents.isPending ? (
          // Loading — skeleton rows shaped like the real list.
          <div className="space-y-2" aria-label="Loading documents">
            <Skeleton className="h-7 w-full rounded-md" />
            <Skeleton className="h-7 w-full rounded-md" />
            <Skeleton className="h-7 w-3/4 rounded-md" />
          </div>
        ) : documents.isError ? (
          // Error — explain and offer retry, never a blank gap.
          <div className="flex flex-col items-center gap-2 rounded-lg border border-error/40 bg-error-soft px-3 py-4 text-center">
            <p className="text-[13px] text-error">Couldn&apos;t load documents</p>
            <button
              type="button"
              onClick={() => documents.refetch()}
              className="rounded-sm border border-border bg-secondary px-2 py-1 text-xs transition-colors duration-150 hover:bg-accent"
            >
              Retry
            </button>
          </div>
        ) : files.length > 0 ? (
          <ul className="flex flex-col gap-1">
            {files.map((name) => (
              <li
                key={name}
                className="flex items-center gap-2 truncate rounded-md px-2 py-1.5 text-[13px] transition-colors duration-150 hover:bg-sidebar-accent"
              >
                <FileText
                  className="size-4 shrink-0 text-muted-foreground"
                  aria-hidden
                />
                <span className="truncate">{name}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="flex flex-col items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-5 text-center">
            <FolderOpen className="size-4 text-muted-foreground" aria-hidden />
            <p className="text-[13px] text-muted-foreground">
              No documents yet
            </p>
            <p className="text-xs text-muted-foreground/70">
              Uploaded files will appear here
            </p>
          </div>
        )}
      </div>

      {/* Database — live document count + the clear action. */}
      <div className="flex flex-col gap-3">
        <SectionLabel>Database</SectionLabel>
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center gap-2">
            <Database className="size-4 text-muted-foreground" aria-hidden />
            <span className="text-2xl font-semibold tabular-nums">
              {documents.isSuccess ? files.length : "—"}
            </span>
          </div>
          <p className="mt-1 text-[13px] text-muted-foreground">
            document{files.length === 1 ? "" : "s"} indexed
          </p>
          <button
            type="button"
            disabled={clearDb.isPending || files.length === 0}
            onClick={confirmClear}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-sm border border-border bg-secondary px-2 py-1.5 text-xs transition-colors duration-150 hover:border-error/40 hover:bg-error-soft hover:text-error disabled:cursor-not-allowed disabled:opacity-50"
          >
            {clearDb.isPending ? (
              <Loader2 className="size-3 animate-spin" aria-hidden />
            ) : (
              <Trash2 className="size-3" aria-hidden />
            )}
            Clear database
          </button>
        </div>
      </div>

      {/* Settings — full model details arrive with GET /status (3B). */}
      <div className="flex flex-col gap-3">
        <SectionLabel>Settings</SectionLabel>
        <button
          type="button"
          onClick={() =>
            toast.info("Model details arrive with the /status wiring", {
              description: "Phase 3B connects the remaining endpoints.",
            })
          }
          className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-[13px] transition-colors duration-150 hover:bg-sidebar-accent"
        >
          <span className="flex items-center gap-2">
            <Settings className="size-4 text-muted-foreground" aria-hidden />
            Model details
          </span>
          <ChevronRight className="size-4 text-muted-foreground" aria-hidden />
        </button>
      </div>

      {/* Footer pinned to the bottom of the sidebar — DESIGN.md §10. */}
      <div className="mt-auto border-t border-sidebar-border pt-4">
        <p className="text-xs leading-relaxed text-muted-foreground">
          Built with
          <br />
          <span className="font-semibold text-foreground">
            FastAPI · ChromaDB · Ollama · Next.js
          </span>
        </p>
      </div>
    </aside>
  );
}
