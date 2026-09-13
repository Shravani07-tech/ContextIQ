"use client";

import { Database, FileText, FolderOpen, Loader2, Trash2 } from "lucide-react";

import { CollectionList } from "@/components/sidebar/collection-list";
import { DocumentLibraryDialog } from "@/components/sidebar/document-library-dialog";
import { ModelDetailsDialog } from "@/components/sidebar/model-details-dialog";
import { UploadDropzone } from "@/components/sidebar/upload-dropzone";
import { EmptyPanelState } from "@/components/shared/empty-panel-state";
import { InlineError } from "@/components/shared/inline-error";
import { Skeleton } from "@/components/ui/skeleton";
import { confirmToast } from "@/lib/confirm-toast";

import { useActiveCollection } from "@/hooks/useCollections";
import { useClearDatabase } from "@/hooks/useDatabase";
import { useDocuments } from "@/hooks/useDocuments";
import { useChat } from "@/hooks/useChat";
import { useStatus } from "@/hooks/useStatus";

const MAX_VISIBLE_FILES = 5;

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-bold uppercase tracking-[0.06em] text-muted-foreground">
      {children}
    </p>
  );
}

export function Sidebar() {
  const [activeCollectionId] = useActiveCollection();
  const documents = useDocuments(
    activeCollectionId ? { collection_id: activeCollectionId } : undefined,
  );
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
    <aside className="flex h-full w-[280px] flex-col gap-5 border-r border-sidebar-border bg-sidebar p-4 overflow-y-auto">
      {/* Brand lockup */}
      <div className="flex items-start gap-3">
        <div className="flex size-[34px] shrink-0 items-center justify-center rounded-md bg-sidebar-primary text-[15px] font-extrabold text-sidebar-primary-foreground">
          C
        </div>
        <div className="min-w-0">
          <p className="text-[15px] font-bold leading-tight">ContextIQ</p>
          <p className="text-xs leading-tight text-muted-foreground">
            Private AI Knowledge Workspace
          </p>
        </div>
      </div>

      {/* Collections Scope section */}
      <CollectionList />

      {/* Knowledge base — upload + indexed files */}
      <div className="flex flex-col gap-3">
        <SectionLabel>Knowledge Base</SectionLabel>

        <UploadDropzone />

        {documents.isPending ? (
          <div className="space-y-2" aria-label="Loading documents">
            <Skeleton className="h-7 w-full rounded-md" />
            <Skeleton className="h-7 w-full rounded-md" />
            <Skeleton className="h-7 w-3/4 rounded-md" />
          </div>
        ) : documents.isError ? (
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
            title="No documents in scope"
            description="Uploaded files will appear here"
          />
        )}

        {files.length > MAX_VISIBLE_FILES && (
          <p className="px-2 text-xs text-muted-foreground">
            +{files.length - MAX_VISIBLE_FILES} more
          </p>
        )}

        <DocumentLibraryDialog />
      </div>

      {/* Database section */}
      <div className="flex flex-col gap-3">
        <SectionLabel>Database</SectionLabel>
        <div className="rounded-lg border border-border bg-card p-3">
          <div className="flex items-center gap-2">
            <Database className="size-4 text-muted-foreground" aria-hidden />
            <span className="text-xl font-semibold tabular-nums">
              {documents.isSuccess ? files.length : "—"}
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            doc{files.length === 1 ? "" : "s"} in scope
            {status.data ? ` · ${status.data.vector_count} vectors total` : ""}
          </p>
          <button
            type="button"
            disabled={clearDb.isPending || files.length === 0}
            onClick={confirmClear}
            className="mt-2.5 flex w-full items-center justify-center gap-2 rounded-sm border border-border bg-secondary px-2 py-1.5 text-xs transition-colors duration-150 hover:border-error/40 hover:bg-error-soft hover:text-error disabled:cursor-not-allowed disabled:opacity-50"
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

      {/* Settings section */}
      <div className="flex flex-col gap-3">
        <SectionLabel>Settings</SectionLabel>
        <ModelDetailsDialog />
      </div>

      {/* Footer */}
      <div className="mt-auto border-t border-sidebar-border pt-3">
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
