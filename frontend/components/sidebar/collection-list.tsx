"use client";

import { Folder, Globe, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  useActiveCollection,
  useCollections,
  useCreateCollection,
  useDeleteCollection,
} from "@/hooks/useCollections";
import { confirmToast } from "@/lib/confirm-toast";
import type { Collection } from "@/lib/types";

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-bold uppercase tracking-[0.06em] text-muted-foreground">
      {children}
    </p>
  );
}

export function CollectionList() {
  const [activeCollectionId, setActiveCollectionId] = useActiveCollection();
  const { data: collections = [] } = useCollections();
  const createMutation = useCreateCollection();
  const deleteMutation = useDeleteCollection();

  const [isOpen, setIsOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color] = useState("#3B82F6");

  const activeCollection = collections.find((c: Collection) => c.id === activeCollectionId);

  function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;

    createMutation.mutate(
      { name: name.trim(), description: description.trim(), color },
      {
        onSuccess: (newColl: Collection) => {
          setIsOpen(false);
          setName("");
          setDescription("");
          setActiveCollectionId(newColl.id);
        },
      },
    );
  }

  function confirmDeleteCollection(collId: string, collName: string) {
    confirmToast({
      title: `Delete collection '${collName}'?`,
      description: "Documents inside will revert to Uncategorized. Vector embeddings remain safe.",
      actionLabel: "Delete Collection",
      onConfirm: () => deleteMutation.mutate(collId),
    });
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <SectionLabel>Collections Scope</SectionLabel>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger
            render={
              <button
                type="button"
                aria-label="Create collection"
                className="flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground"
              />
            }
          >
            <Plus className="size-3.5" aria-hidden />
            <span>New</span>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>New Collection</DialogTitle>
              <DialogDescription>
                Create a knowledge workspace to organize related documents.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4 pt-2">
              <div>
                <label className="mb-1 block text-xs font-semibold">Name</label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Zephyra Research"
                  required
                  className="h-9"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold">Description (Optional)</label>
                <Input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. Market analysis & competitor notes"
                  className="h-9"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsOpen(false)}
                  className="rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-accent"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || !name.trim()}
                  className="rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50"
                >
                  {createMutation.isPending ? "Creating..." : "Create Collection"}
                </button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <ul className="flex flex-col gap-1">
        {/* Global Scope / All Documents option */}
        <li
          onClick={() => setActiveCollectionId(null)}
          className={`flex cursor-pointer items-center justify-between rounded-md px-2.5 py-1.5 text-[13px] transition-colors ${
            activeCollectionId === null
              ? "bg-sidebar-primary text-sidebar-primary-foreground font-semibold"
              : "hover:bg-sidebar-accent text-foreground"
          }`}
        >
          <div className="flex items-center gap-2 truncate">
            <Globe className="size-4 shrink-0" />
            <span className="truncate">All Documents (Global)</span>
          </div>
        </li>

        {/* Collections */}
        {collections.map((coll: Collection) => {
          const isSelected = activeCollectionId === coll.id;
          return (
            <li
              key={coll.id}
              onClick={() => setActiveCollectionId(coll.id)}
              className={`group flex cursor-pointer items-center justify-between rounded-md px-2.5 py-1.5 text-[13px] transition-colors ${
                isSelected
                  ? "bg-sidebar-primary text-sidebar-primary-foreground font-semibold"
                  : "hover:bg-sidebar-accent text-foreground"
              }`}
            >
              <div className="flex items-center gap-2 truncate">
                <Folder
                  className="size-4 shrink-0"
                  style={{ color: isSelected ? "inherit" : coll.color || "#3B82F6" }}
                />
                <span className="truncate">{coll.name}</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="rounded-full bg-sidebar-border px-1.5 py-0.2 text-[10px] text-muted-foreground group-hover:text-foreground">
                  {coll.document_count}
                </span>
                <button
                  type="button"
                  aria-label={`Delete ${coll.name}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    confirmDeleteCollection(coll.id, coll.name);
                  }}
                  className="hidden rounded p-0.5 hover:bg-error-soft hover:text-error group-hover:block"
                >
                  <Trash2 className="size-3" />
                </button>
              </div>
            </li>
          );
        })}
      </ul>

      {/* Scope Badge indicator */}
      <div className="rounded-md border border-sidebar-border bg-sidebar-accent/50 px-2.5 py-1.5 text-xs">
        <span className="text-muted-foreground">Active Scope: </span>
        <span className="font-semibold text-foreground">
          {activeCollection ? `📁 ${activeCollection.name}` : "🌐 All Documents"}
        </span>
      </div>
    </div>
  );
}
