"use client";

// Upload workflow hook: client-side validation -> staged upload with
// byte-level progress (cancellable) -> indexing -> cache refresh +
// client-side metadata capture, with per-file toast reporting
// throughout.
//
// Duplicate handling: the backend treats a re-uploaded filename as a
// replacement (its old chunks are deleted before the new ones are
// written), so duplicates are allowed and reported as "updated"
// rather than rejected — re-uploading an edited file is the normal
// way to refresh it.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { useDocumentMeta } from "@/hooks/useDocumentMeta";
import { api } from "@/lib/api";
import type { DocumentsResponse, FileResult } from "@/lib/types";

const ALLOWED_EXTENSIONS = [".pdf", ".txt"];
// Sanity cap — a local embedding pipeline chokes on giant files long
// before this, so fail fast with a clear message instead.
const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB
// How long the explicit success/error phase holds before settling
// back to idle — long enough to register as a deliberate state, not
// just a flash.
const OUTCOME_DISPLAY_MS = 1800;

export type UploadPhase = "idle" | "uploading" | "indexing" | "success" | "error";

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
  const { recordUpload } = useDocumentMeta();
  const [phase, setPhase] = useState<UploadPhase>("idle");
  const [progress, setProgress] = useState(0);
  // Outcome of the most recent batch, for the dropzone's inline
  // success/failure rows — a more persistent visual record than the
  // toasts, which disappear on their own.
  const [lastResults, setLastResults] = useState<FileResult[]>([]);
  // Holds the in-flight XHR's abort handle so cancelUpload() (called
  // from a button, outside the mutationFn's own scope) can reach it.
  const cancelRef = useRef<(() => void) | null>(null);
  // Holds the pending "settle back to idle" timer so a new upload
  // starting mid-display can cancel a stale one instead of it firing
  // setPhase("idle") in the middle of the NEW upload.
  const outcomeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function clearOutcomeTimer() {
    if (outcomeTimerRef.current) {
      clearTimeout(outcomeTimerRef.current);
      outcomeTimerRef.current = null;
    }
  }

  useEffect(() => clearOutcomeTimer, []);

  const mutation = useMutation({
    mutationFn: async (files: File[]) => {
      // Names already in the knowledge base -> these become "updated"
      // in the report instead of "indexed".
      const existing = new Set(
        queryClient.getQueryData<DocumentsResponse>(["documents"])?.documents ??
          [],
      );
      // filename -> original File, so a successful index result can
      // be paired back up with the real byte size for useDocumentMeta.
      const sizeByName = new Map(files.map((f) => [f.name, f.size]));

      setPhase("uploading");
      setProgress(0);
      const { promise, cancel } = api.upload(files, setProgress);
      cancelRef.current = cancel;
      const uploaded = await promise;
      cancelRef.current = null;

      const saved = uploaded.files
        .filter((f) => f.status === "saved")
        .map((f) => f.filename);
      const serverRejected = uploaded.files.filter(
        (f) => f.status === "error",
      );

      setPhase("indexing");
      const indexed = saved.length > 0 ? await api.index(saved) : null;

      return { indexed: indexed?.files ?? [], serverRejected, existing, sizeByName };
    },
    onSuccess: ({ indexed, serverRejected, existing, sizeByName }) => {
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
          // Real size (from the File object we uploaded) + real chunk
          // count (from this exact index response) + now — the three
          // fields the document library shows that the backend has
          // nowhere to persist today.
          const sizeBytes = sizeByName.get(f.filename);
          if (sizeBytes !== undefined && f.chunks_indexed != null) {
            recordUpload(f.filename, { sizeBytes, chunks: f.chunks_indexed });
          }
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
      setLastResults([...indexed, ...serverRejected]);
      // Refresh every consumer of the document list AND the status
      // counts (vector count changes with each indexing run).
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["status"] });

      // Explicit success state IN the dropzone itself, not just the
      // toasts (which disappear on their own) — held briefly, then
      // settles to idle.
      setPhase("success");
      clearOutcomeTimer();
      outcomeTimerRef.current = setTimeout(
        () => setPhase("idle"),
        OUTCOME_DISPLAY_MS,
      );
    },
    onError: (error) => {
      cancelRef.current = null;
      // A user-initiated cancel isn't a failure — say so distinctly
      // rather than showing a red "Upload failed" for something the
      // user asked for, and skip the error phase entirely (nothing
      // went wrong; go straight back to idle).
      if (error.message === "Upload cancelled.") {
        toast.info("Upload cancelled");
        setPhase("idle");
        return;
      }
      toast.error("Upload failed", { description: error.message });
      setPhase("error");
      clearOutcomeTimer();
      outcomeTimerRef.current = setTimeout(
        () => setPhase("idle"),
        OUTCOME_DISPLAY_MS,
      );
    },
    onSettled: () => {
      setProgress(0);
    },
  });

  /** Validate then upload; invalid files get error toasts and never
      leave the browser. */
  function uploadFiles(files: File[]) {
    if (mutation.isPending) return;
    clearOutcomeTimer(); // a fresh batch pre-empts any pending revert-to-idle
    setLastResults([]); // clear the previous batch's rows immediately
    const { valid, rejected } = validate(files);
    for (const r of rejected) {
      toast.error(`Rejected ${r.name}`, { description: r.reason });
    }
    if (valid.length > 0) mutation.mutate(valid);
  }

  /** Abort the in-flight upload, if any. No-op once indexing has
      already started — that request has no cancel handle, and the
      files are already safely staged server-side by that point. */
  function cancelUpload() {
    cancelRef.current?.();
  }

  return {
    uploadFiles,
    cancelUpload,
    phase,
    progress,
    lastResults,
    isPending: mutation.isPending,
  };
}
