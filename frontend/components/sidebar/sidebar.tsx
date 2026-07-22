"use client";

// Sidebar — now fully live: document list from GET /documents,
// uploads through POST /upload + /index, clearing via
// DELETE /database (gated behind a confirmation toast). Loading
// renders skeleton rows; errors render a retry card — never a blank
// gap. Layout and styling are unchanged from Phase 2.

import { Database, FileText, FolderOpen, Loader2, Trash2 } from "lucide-react";

import { DocumentLibraryDialog } from "@/components/sidebar/document-library-dialog";
import { ModelDetailsDialog } from "@/components/sidebar/model-details-dialog";
import { UploadDropzone } from "@/components/sidebar/upload-dropzone";
import { EmptyPanelState } from "@/components/shared/empty-panel-state";
import { InlineError } from "@/components/shared/inline-error";
import { Skeleton } from "@/components/ui/skeleton";
import { confirmToast } from "@/lib/confirm-toast";
import { useClearDatabase } from "@/hooks/useDatabase";
import { useDocuments } from "@/hooks/useDocuments";
import { useChat } from "@/hooks/useChat";
import { useStatus } from "@/hooks/useStatus";

// The compact sidebar list is a glance, not the full manager — cap
// it and point to the Document Library dialog for everything beyond.
const MAX_VISIBLE_FILES = 5;

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
  const status = useStatus();
  const clearDb = useClearDatabase();
  const { addSystemMessage } = useChat();

  const files = documents.data ?? [];

  function confirmClear() {
    confirmToast({
      title: "Clear the entire knowledge base?",
      description: "Every vector is deleted. Files on disk are kept.",
      actionLabel: "Clear",
      onConfirm: () =>
        clearDb.mutate(undefined, {
          onSuccess: () => addSystemMessage("Knowledge base cleared"),
        }),
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
          <InlineError
            message="Couldn't load documents"
            onRetry={() => documents.refetch()}
            className="py-4"
          />
        ) : files.length > 0 ? (
          <ul className="flex flex-col gap-1">
            {files.slice(0, MAX_VISIBLE_FILES).map((name) => (
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
          <EmptyPanelState
            icon={FolderOpen}
            title="No documents yet"
            description="Uploaded files will appear here"
          />
        )}

        {files.length > MAX_VISIBLE_FILES && (
          <p className="px-2 text-xs text-muted-foreground">
            +{files.length - MAX_VISIBLE_FILES} more
          </p>
        )}

        {files.length > 0 && <DocumentLibraryDialog />}
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
            {status.data ? ` · ${status.data.vector_count} vectors` : ""}
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

      {/* Settings — live pipeline configuration from GET /status,
          via a proper dialog rather than a toast that vanishes and
          can't be re-consulted. */}
      <div className="flex flex-col gap-3">
        <SectionLabel>Settings</SectionLabel>
        <ModelDetailsDialog />
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
