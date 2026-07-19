"use client";

// Upload workflow hook: client-side validation -> staged upload with
// byte-level progress -> indexing -> cache refresh, with per-file
// toast reporting throughout.
//
// Duplicate handling: the backend treats a re-uploaded filename as a
// replacement (its old chunks are deleted before the new ones are
// written), so duplicates are allowed and reported as "updated"
// rather than rejected — re-uploading an edited file is the normal
// way to refresh it.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { DocumentsResponse } from "@/lib/types";

const ALLOWED_EXTENSIONS = [".pdf", ".txt"];
// Sanity cap — a local embedding pipeline chokes on giant files long
// before this, so fail fast with a clear message instead.
const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB

export type UploadPhase = "idle" | "uploading" | "indexing";

interface RejectedFile {
  name: string;
  reason: string;
}

/** Split a picked/dropped selection into valid files and rejects. */
function validate(files: File[]): { valid: File[]; rejected: RejectedFile[] } {
  const valid: File[] = [];
  const rejected: RejectedFile[] = [];
  for (const file of files) {
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      rejected.push({
        name: file.name,
        reason: "Only PDF and TXT files are supported",
      });
    } else if (file.size > MAX_FILE_SIZE) {
      rejected.push({ name: file.name, reason: "File is larger than 25 MB" });
    } else if (file.size === 0) {
      rejected.push({ name: file.name, reason: "File is empty" });
    } else {
      valid.push(file);
    }
  }
  return { valid, rejected };
}

export function useUpload() {
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<UploadPhase>("idle");
  const [progress, setProgress] = useState(0);

  const mutation = useMutation({
    mutationFn: async (files: File[]) => {
      // Names already in the knowledge base -> these become "updated"
      // in the report instead of "indexed".
      const existing = new Set(
        queryClient.getQueryData<DocumentsResponse>(["documents"])?.documents ??
          [],
      );

      setPhase("uploading");
      setProgress(0);
      const uploaded = await api.upload(files, setProgress);

      const saved = uploaded.files
        .filter((f) => f.status === "saved")
        .map((f) => f.filename);
      const serverRejected = uploaded.files.filter(
        (f) => f.status === "error",
      );

      setPhase("indexing");
      const indexed = saved.length > 0 ? await api.index(saved) : null;

      return { indexed: indexed?.files ?? [], serverRejected, existing };
    },
    onSuccess: ({ indexed, serverRejected, existing }) => {
      for (const f of indexed) {
        if (f.status === "indexed") {
          const isUpdate = existing.has(f.filename);
          toast.success(
            isUpdate ? `Updated ${f.filename}` : `Indexed ${f.filename}`,
            {
              description: isUpdate
                ? `Previous version replaced · ${f.chunks_indexed} chunk(s)`
                : `${f.chunks_indexed} chunk(s) added to the knowledge base`,
            },
          );
        } else {
          toast.error(`Failed to index ${f.filename}`, {
            description: f.error ?? undefined,
          });
        }
      }
      for (const f of serverRejected) {
        toast.error(`Rejected ${f.filename}`, {
          description: f.error ?? undefined,
        });
      }
      // One invalidation refreshes every consumer of the document
      // list: sidebar files, database status card, knowledge stats.
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (error) => {
      toast.error("Upload failed", { description: error.message });
    },
    onSettled: () => {
      setPhase("idle");
      setProgress(0);
    },
  });

  /** Validate then upload; invalid files get error toasts and never
      leave the browser. */
  function uploadFiles(files: File[]) {
    if (mutation.isPending) return;
    const { valid, rejected } = validate(files);
    for (const r of rejected) {
      toast.error(`Rejected ${r.name}`, { description: r.reason });
    }
    if (valid.length > 0) mutation.mutate(valid);
  }

  return {
    uploadFiles,
    phase,
    progress,
    isPending: mutation.isPending,
  };
}
