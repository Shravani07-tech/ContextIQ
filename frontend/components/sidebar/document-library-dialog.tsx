"use client";

// Document library — the roomier management view the compact
// sidebar list can't fit: search, per-document upload time/size/
// chunk count (client-side metadata; see DocumentMeta in lib/types.ts
// for why), indexed status, and single-file delete. Triggered from
// a button in the sidebar's Knowledge Base section.

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  CheckCircle2,
  Clock,
  FileText,
  Library,
  Loader2,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { useState } from "react";

import { EmptyPanelState } from "@/components/shared/empty-panel-state";
import { InlineError } from "@/components/shared/inline-error";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useDeleteDocument } from "@/hooks/useDeleteDocument";
import { useDocumentMeta } from "@/hooks/useDocumentMeta";
import { useDocuments } from "@/hooks/useDocuments";
import { confirmToast } from "@/lib/confirm-toast";
import { formatBytes, formatDateTime } from "@/lib/utils";

export function DocumentLibraryDialog() {
  const [query, setQuery] = useState("");
  const documents = useDocuments();
  const { meta } = useDocumentMeta();
  const deleteMutation = useDeleteDocument();
  const reduceMotion = useReducedMotion();

  const files = documents.data ?? [];
  const trimmedQuery = query.trim().toLowerCase();
  const filtered = trimmedQuery
    ? files.filter((name) => name.toLowerCase().includes(trimmedQuery))
    : files;

  function confirmDelete(filename: string) {
    confirmToast({
      title: `Delete ${filename}?`,
      description: "This removes it from the knowledge base permanently.",
      actionLabel: "Delete",
      onConfirm: () => deleteMutation.mutate(filename),
    });
  }

  return (
    <Dialog>
      {/* Base UI composition: `render` supplies the element, children
          render inside it — same pattern as the Sheet trigger. */}
      <DialogTrigger
        render={
          <button
            type="button"
            className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-[13px] transition-colors duration-150 hover:bg-sidebar-accent"
          />
        }
      >
        <span className="flex items-center gap-2">
          <Library className="size-4 text-muted-foreground" aria-hidden />
          Manage documents
        </span>
      </DialogTrigger>

      <DialogContent className="max-h-[85vh] max-w-[calc(100%-2rem)] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Document Library</DialogTitle>
          <DialogDescription>
            {documents.isSuccess
              ? `${files.length} document${files.length === 1 ? "" : "s"} indexed`
              : "Manage your indexed documents"}
          </DialogDescription>
        </DialogHeader>

        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search documents..."
            aria-label="Search documents"
            className="h-9 px-8"
          />
          {query.length > 0 && (
            <button
              type="button"
              onClick={() => setQuery("")}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 flex size-5 -translate-y-1/2 items-center justify-center rounded-sm text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground"
            >
              <X className="size-3.5" aria-hidden />
            </button>
          )}
        </div>

        <div className="max-h-[50vh] overflow-y-auto">
          {documents.isPending ? (
            <div className="space-y-2" aria-label="Loading documents">
              <Skeleton className="h-16 rounded-md" />
              <Skeleton className="h-16 rounded-md" />
              <Skeleton className="h-16 rounded-md" />
            </div>
          ) : documents.isError ? (
            <InlineError
              message="Couldn't load documents"
              onRetry={() => documents.refetch()}
            />
          ) : files.length === 0 ? (
            <EmptyPanelState
              icon={Library}
              title="No documents yet"
              description="Upload PDF or TXT files to build your knowledge base"
            />
          ) : filtered.length === 0 ? (
            <EmptyPanelState
              icon={Search}
              title="No matches"
              description={`No documents match "${query.trim()}"`}
            />
          ) : (
            <ul className="flex flex-col gap-2">
              <AnimatePresence initial={false}>
                {filtered.map((filename) => {
                  const docMeta = meta[filename];
                  const isDeletingThis =
                    deleteMutation.isPending &&
                    deleteMutation.variables === filename;

                  return (
                    <motion.li
                      key={filename}
                      layout={!reduceMotion}
                      initial={reduceMotion ? false : { opacity: 0, y: 4 }}
                      animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
                      exit={reduceMotion ? undefined : { opacity: 0, height: 0 }}
                      transition={{ duration: 0.18, ease: "easeOut" }}
                      className="flex items-start justify-between gap-2 rounded-md border border-border bg-card p-3"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <FileText
                            className="size-4 shrink-0 text-muted-foreground"
                            aria-hidden
                          />
                          <p className="min-w-0 truncate text-[13px] font-semibold">
                            {filename}
                          </p>
                        </div>
                        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Clock className="size-3" aria-hidden />
                            {docMeta ? formatDateTime(docMeta.uploadedAt) : "—"}
                          </span>
                          <span>
                            {docMeta ? formatBytes(docMeta.sizeBytes) : "—"}
                          </span>
                          <span>
                            {docMeta
                              ? `${docMeta.chunks} chunk${docMeta.chunks === 1 ? "" : "s"}`
                              : "— chunks"}
                          </span>
                          {/* Always true today: GET /documents only
                              ever lists files that ARE indexed. */}
                          <span className="flex items-center gap-1 text-success">
                            <CheckCircle2 className="size-3" aria-hidden />
                            Indexed
                          </span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => confirmDelete(filename)}
                        disabled={deleteMutation.isPending}
                        aria-label={`Delete ${filename}`}
                        className="flex shrink-0 items-center justify-center rounded-sm p-1.5 text-muted-foreground transition-colors duration-150 hover:bg-error-soft hover:text-error disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {isDeletingThis ? (
                          <Loader2 className="size-4 animate-spin" aria-hidden />
                        ) : (
                          <Trash2 className="size-4" aria-hidden />
                        )}
                      </button>
                    </motion.li>
                  );
                })}
              </AnimatePresence>
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
