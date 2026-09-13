"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  CheckCircle2,
  FileText,
  Library,
  Loader2,
  Plus,
  Search,
  Tag,
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
import {
  useAddTag,
  useDetailedDocuments,
  useMoveDocument,
  useRemoveTag,
  useTags,
} from "@/hooks/useDocuments";
import { useCollections } from "@/hooks/useCollections";
import { confirmToast } from "@/lib/confirm-toast";
import { formatBytes } from "@/lib/utils";
import type { Collection, DocumentDetail } from "@/lib/types";


export function DocumentLibraryDialog() {
  const [query, setQuery] = useState("");
  const [selectedTagFilter, setSelectedTagFilter] = useState<string | null>(null);
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string | null>(null);
  const [tagInputDoc, setTagInputDoc] = useState<string | null>(null);
  const [newTagText, setNewTagText] = useState("");

  const detailedDocsQuery = useDetailedDocuments();
  const collectionsQuery = useCollections();
  const tagsQuery = useTags();
  const deleteMutation = useDeleteDocument();
  const moveMutation = useMoveDocument();
  const addTagMutation = useAddTag();
  const removeTagMutation = useRemoveTag();
  const reduceMotion = useReducedMotion();

  const documents = detailedDocsQuery.data ?? [];
  const collections = collectionsQuery.data ?? [];
  const allTags = tagsQuery.data ?? [];

  const trimmedQuery = query.trim().toLowerCase();

  const filtered = documents.filter((doc: DocumentDetail) => {
    if (trimmedQuery && !doc.filename.toLowerCase().includes(trimmedQuery)) {
      return false;
    }
    if (selectedTypeFilter && doc.file_type.toLowerCase() !== selectedTypeFilter.toLowerCase()) {
      return false;
    }
    if (selectedTagFilter && !doc.tags.includes(selectedTagFilter)) {
      return false;
    }
    return true;
  });


  function confirmDelete(filename: string) {
    confirmToast({
      title: `Delete ${filename}?`,
      description: "This removes it from the knowledge base permanently.",
      actionLabel: "Delete",
      onConfirm: () => deleteMutation.mutate(filename),
    });
  }

  function handleAddTagSubmit(filename: string, e: React.FormEvent) {
    e.preventDefault();
    if (!newTagText.trim()) return;
    addTagMutation.mutate(
      { filename, tag: newTagText.trim() },
      {
        onSuccess: () => {
          setTagInputDoc(null);
          setNewTagText("");
        },
      },
    );
  }

  return (
    <Dialog>
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
          Manage documents & metadata
        </span>
      </DialogTrigger>

      <DialogContent className="max-h-[85vh] max-w-[calc(100%-2rem)] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Document Library & Workspace Metadata</DialogTitle>
          <DialogDescription>
            {detailedDocsQuery.isSuccess
              ? `${documents.length} document${documents.length === 1 ? "" : "s"} indexed in workspace`
              : "Manage your indexed documents"}
          </DialogDescription>
        </DialogHeader>

        {/* Search & Filter Bar */}
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1">
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
                className="absolute right-2 top-1/2 flex size-5 -translate-y-1/2 items-center justify-center rounded-sm text-muted-foreground hover:bg-accent hover:text-foreground"
              >
                <X className="size-3.5" aria-hidden />
              </button>
            )}
          </div>

          {/* Filters */}
          <div className="flex items-center gap-2 text-xs">
            {/* File Type Filter */}
            <select
              value={selectedTypeFilter || ""}
              onChange={(e) => setSelectedTypeFilter(e.target.value || null)}
              className="h-9 rounded-md border border-border bg-background px-2 text-xs text-foreground focus:outline-none"
            >
              <option value="">All Types</option>
              <option value="pdf">PDF</option>
              <option value="txt">TXT</option>
              <option value="docx">DOCX</option>
              <option value="pptx">PPTX</option>
              <option value="xlsx">XLSX</option>
              <option value="csv">CSV</option>
              <option value="md">Markdown</option>
              <option value="html">HTML</option>
            </select>

            {/* Tag Filter */}
            <select
              value={selectedTagFilter || ""}
              onChange={(e) => setSelectedTagFilter(e.target.value || null)}
              className="h-9 rounded-md border border-border bg-background px-2 text-xs text-foreground focus:outline-none"
            >
              <option value="">All Tags</option>
              {allTags.map((t: string) => (
                <option key={t} value={t}>
                  #{t}
                </option>
              ))}
            </select>

          </div>
        </div>

        <div className="max-h-[55vh] overflow-y-auto">
          {detailedDocsQuery.isPending ? (
            <div className="space-y-2" aria-label="Loading documents">
              <Skeleton className="h-24 rounded-md" />
              <Skeleton className="h-24 rounded-md" />
              <Skeleton className="h-24 rounded-md" />
            </div>
          ) : detailedDocsQuery.isError ? (
            <InlineError
              message="Couldn't load document details"
              onRetry={() => detailedDocsQuery.refetch()}
            />
          ) : documents.length === 0 ? (
            <EmptyPanelState
              icon={Library}
              title="No documents yet"
              description="Upload files to build your knowledge base"
            />
          ) : filtered.length === 0 ? (
            <EmptyPanelState
              icon={Search}
              title="No matches"
              description="No documents match your active search or filters"
            />
          ) : (
            <ul className="flex flex-col gap-2.5">
              <AnimatePresence initial={false}>
                {filtered.map((doc: DocumentDetail) => {
                  const isDeletingThis =
                    deleteMutation.isPending &&
                    deleteMutation.variables === doc.filename;

                  return (
                    <motion.li
                      key={doc.filename}
                      layout={!reduceMotion}
                      initial={reduceMotion ? false : { opacity: 0, y: 4 }}
                      animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
                      exit={reduceMotion ? undefined : { opacity: 0, height: 0 }}
                      transition={{ duration: 0.18, ease: "easeOut" }}
                      className="flex flex-col gap-2 rounded-md border border-border bg-card p-3"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <FileText
                              className="size-4 shrink-0 text-muted-foreground"
                              aria-hidden
                            />
                            <p className="min-w-0 truncate text-[13px] font-semibold">
                              {doc.filename}
                            </p>
                            <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-medium uppercase text-secondary-foreground">
                              {doc.file_type}
                            </span>
                            {doc.extraction_method === "ocr" && (
                              <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-amber-500">
                                OCR
                              </span>
                            )}
                          </div>

                          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                            <span>{formatBytes(doc.file_size)}</span>
                            <span>{doc.chunk_count} chunk(s)</span>
                            <span className="flex items-center gap-1 text-success">
                              <CheckCircle2 className="size-3" aria-hidden />
                              Indexed
                            </span>
                          </div>
                        </div>

                        {/* Collection Selector & Delete button */}
                        <div className="flex items-center gap-2">
                          <select
                            value={doc.collection_id || ""}
                            onChange={(e) =>
                              moveMutation.mutate({
                                filename: doc.filename,
                                collectionId: e.target.value || null,
                              })
                            }
                            disabled={moveMutation.isPending}
                            className="h-8 rounded border border-border bg-background px-2 text-xs text-foreground focus:outline-none"
                          >
                            <option value="">Uncategorized</option>
                            {collections.map((c: Collection) => (
                              <option key={c.id} value={c.id}>
                                📁 {c.name}
                              </option>
                            ))}
                          </select>


                          <button
                            type="button"
                            onClick={() => confirmDelete(doc.filename)}
                            disabled={deleteMutation.isPending}
                            aria-label={`Delete ${doc.filename}`}
                            className="flex shrink-0 items-center justify-center rounded-sm p-1.5 text-muted-foreground transition-colors hover:bg-error-soft hover:text-error disabled:opacity-50"
                          >
                            {isDeletingThis ? (
                              <Loader2 className="size-4 animate-spin" aria-hidden />
                            ) : (
                              <Trash2 className="size-4" aria-hidden />
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Document Tags Section */}
                      <div className="flex flex-wrap items-center gap-1.5 pt-1 text-xs border-t border-border/40">
                        <Tag className="size-3 text-muted-foreground shrink-0" />
                        {doc.tags.map((t) => (
                          <span
                            key={t}
                            className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary"
                          >
                            #{t}
                            <button
                              type="button"
                              onClick={() =>
                                removeTagMutation.mutate({
                                  filename: doc.filename,
                                  tag: t,
                                })
                              }
                              className="rounded-full hover:bg-primary/20 p-0.5"
                            >
                              <X className="size-2.5" />
                            </button>
                          </span>
                        ))}

                        {tagInputDoc === doc.filename ? (
                          <form
                            onSubmit={(e) => handleAddTagSubmit(doc.filename, e)}
                            className="inline-flex items-center gap-1"
                          >
                            <Input
                              value={newTagText}
                              onChange={(e) => setNewTagText(e.target.value)}
                              placeholder="tag name..."
                              autoFocus
                              className="h-6 w-24 px-1.5 text-xs"
                            />
                            <button
                              type="submit"
                              className="rounded bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground"
                            >
                              Add
                            </button>
                            <button
                              type="button"
                              onClick={() => setTagInputDoc(null)}
                              className="text-muted-foreground hover:text-foreground"
                            >
                              <X className="size-3" />
                            </button>
                          </form>
                        ) : (
                          <button
                            type="button"
                            onClick={() => {
                              setTagInputDoc(doc.filename);
                              setNewTagText("");
                            }}
                            className="inline-flex items-center gap-0.5 rounded-full border border-dashed border-border px-2 py-0.5 text-[11px] text-muted-foreground hover:border-primary hover:text-primary"
                          >
                            <Plus className="size-2.5" />
                            <span>Add Tag</span>
                          </button>
                        )}
                      </div>
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
