"use client";

// Scope picker shared by the analysis dialogs. The active collection
// (sidebar) is always the outer boundary; within it the user can keep
// "all documents in scope" or narrow to specific files. The backend
// re-validates the same rule (scope.py), so this is a convenience, not
// the security boundary.

import { Check, Files } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { useActiveCollection, useCollections } from "@/hooks/useCollections";
import { useDetailedDocuments } from "@/hooks/useDocuments";
import { cn } from "@/lib/utils";

export function useScopeLabel(): string {
  const [activeCollectionId] = useActiveCollection();
  const { data: collections } = useCollections();
  if (!activeCollectionId) return "All documents";
  if (activeCollectionId === "uncategorized") return "Uncategorized";
  return collections?.find((c) => c.id === activeCollectionId)?.name ?? "Selected collection";
}

export function ScopePicker({
  selected,
  onChange,
  max = 25,
  label = "Documents",
}: {
  selected: string[];
  onChange: (next: string[]) => void;
  max?: number;
  label?: string;
}) {
  const [activeCollectionId] = useActiveCollection();
  const scopeLabel = useScopeLabel();
  const docs = useDetailedDocuments(
    activeCollectionId ? { collection_id: activeCollectionId } : undefined,
  );
  const available = docs.data ?? [];

  function toggle(name: string) {
    if (selected.includes(name)) onChange(selected.filter((n) => n !== name));
    else if (selected.length < max) onChange([...selected, name]);
  }

  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 flex w-full items-center justify-between text-xs font-medium">
        <span>
          {label} <span className="text-muted-foreground">· scope: {scopeLabel}</span>
        </span>
        {selected.length > 0 && (
          <button
            type="button"
            onClick={() => onChange([])}
            className="rounded-sm px-1 text-xs text-primary hover:underline"
          >
            Use all in scope
          </button>
        )}
      </legend>

      {docs.isPending ? (
        <div className="space-y-1.5" aria-label="Loading documents">
          <Skeleton className="h-7 w-full rounded-md" />
          <Skeleton className="h-7 w-2/3 rounded-md" />
        </div>
      ) : available.length === 0 ? (
        <p className="rounded-md border border-dashed border-border px-3 py-3 text-xs text-muted-foreground">
          No documents in this scope yet. Upload and index files from the sidebar.
        </p>
      ) : (
        <ul className="flex max-h-36 flex-col gap-1 overflow-y-auto pr-1">
          <li className="flex items-center gap-2 px-2 py-1 text-xs text-muted-foreground">
            <Files className="size-3.5" aria-hidden />
            {selected.length === 0
              ? `All ${available.length} document${available.length === 1 ? "" : "s"} in scope`
              : `${selected.length} selected`}
          </li>
          {available.map((doc) => {
            const checked = selected.includes(doc.filename);
            return (
              <li key={doc.filename}>
                <label
                  className={cn(
                    "flex cursor-pointer items-center gap-2 rounded-md border px-2 py-1.5 text-xs transition-colors",
                    checked
                      ? "border-primary/40 bg-primary/5 text-foreground"
                      : "border-border hover:bg-accent",
                  )}
                >
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={checked}
                    onChange={() => toggle(doc.filename)}
                  />
                  <span
                    aria-hidden
                    className={cn(
                      "flex size-3.5 shrink-0 items-center justify-center rounded-[3px] border",
                      checked ? "border-primary bg-primary text-primary-foreground" : "border-border",
                    )}
                  >
                    {checked && <Check className="size-2.5" />}
                  </span>
                  <span className="truncate" title={doc.filename}>
                    {doc.filename}
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      )}
    </fieldset>
  );
}
