"use client";

// Upload dropzone — drag & drop plus click-to-browse, with five
// workflow states cross-faded in place (AnimatePresence mode="wait"
// below — "upload animation" per the UI review):
//   idle      -> icon + "Add or drop PDF / TXT files"
//   uploading -> progress bar with byte-level percentage (XHR) + Cancel
//   indexing  -> spinner (duration depends on the embedding model,
//                so an indeterminate state is the honest one; no
//                cancel here — files are already safely staged)
//   success   -> brief explicit "Upload complete" confirmation
//   error     -> brief explicit "Upload failed" confirmation
// success/error hold for ~1.8s (see useUpload's OUTCOME_DISPLAY_MS)
// before settling back to idle. Below the box: the last batch's
// per-file outcome, as animated success/failure rows — a more
// persistent record than the toasts.
//
// Drag feedback uses the ring-blue border + soft accent tint from
// the design system. A drag-enter/leave counter prevents flicker
// when dragging across child elements.

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  CheckCircle2,
  Loader2,
  UploadCloud,
  X,
  XCircle,
} from "lucide-react";
import { useRef, useState } from "react";

import { useUpload } from "@/hooks/useUpload";

/** Shared cross-fade for the dropzone's phase-conditional content —
    the "upload animation" the box transitions with as it moves
    between idle/uploading/indexing/success/error, instead of
    snapping. Same reduced-motion pattern used app-wide: null (the
    check hasn't resolved yet) is treated as "animate," matching
    app/template.tsx's precedent. */
function crossFadeProps(reduceMotion: boolean | null) {
  return reduceMotion
    ? {}
    : {
        initial: { opacity: 0 },
        animate: { opacity: 1 },
        exit: { opacity: 0 },
        // `as const` keeps "easeOut" a literal type — without it,
        // TS widens it to `string`, which doesn't satisfy Framer
        // Motion's Transition["ease"] (a specific Easing union).
        transition: { duration: 0.15, ease: "easeOut" as const },
      };
}

export function UploadDropzone() {
  const { uploadFiles, cancelUpload, phase, progress, lastResults, isPending } =
    useUpload();
  const inputRef = useRef<HTMLInputElement>(null);
  const dragCounter = useRef(0);
  const [dragActive, setDragActive] = useState(false);
  const reduceMotion = useReducedMotion();

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    dragCounter.current = 0;
    setDragActive(false);
    if (isPending) return;
    uploadFiles(Array.from(e.dataTransfer.files));
  }

  function onDragEnter(e: React.DragEvent) {
    e.preventDefault();
    if (isPending) return;
    dragCounter.current += 1;
    setDragActive(true);
  }

  function onDragLeave(e: React.DragEvent) {
    e.preventDefault();
    dragCounter.current -= 1;
    if (dragCounter.current === 0) setDragActive(false);
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt"
        multiple
        className="hidden"
        onChange={(e) => {
          uploadFiles(Array.from(e.target.files ?? []));
          // Allow re-selecting the same file later.
          e.target.value = "";
        }}
      />

      {/* A plain div, not a button: while uploading it hosts a real
          Cancel <button>, and a button can't contain a button
          (browsers silently break that markup on parse). */}
      <div
        onDrop={onDrop}
        onDragEnter={onDragEnter}
        onDragLeave={onDragLeave}
        onDragOver={(e) => e.preventDefault()}
        className={`rounded-lg border border-dashed p-4 text-center transition-colors duration-150 ${
          dragActive
            ? "border-ring bg-info-soft"
            : "border-input hover:border-ring"
        }`}
      >
        <AnimatePresence mode="wait" initial={false}>
          {phase === "uploading" ? (
            <motion.div
              key="uploading"
              {...crossFadeProps(reduceMotion)}
              className="w-full"
            >
              <div className="flex items-center justify-between gap-2">
                <p className="text-[13px] text-muted-foreground">
                  Uploading… {progress}%
                </p>
                <button
                  type="button"
                  onClick={cancelUpload}
                  aria-label="Cancel upload"
                  className="flex size-6 shrink-0 items-center justify-center rounded-sm text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-error"
                >
                  <X className="size-3.5" aria-hidden />
                </button>
              </div>
              <div
                className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-secondary"
                role="progressbar"
                aria-valuenow={progress}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-150"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </motion.div>
          ) : phase === "indexing" ? (
            <motion.div
              key="indexing"
              {...crossFadeProps(reduceMotion)}
              className="flex flex-col items-center gap-2"
            >
              <Loader2
                className="size-4 animate-spin text-muted-foreground"
                aria-hidden
              />
              <span className="text-[13px] text-muted-foreground">
                Indexing — chunking &amp; embedding…
              </span>
            </motion.div>
          ) : phase === "success" ? (
            <motion.div
              key="success"
              role="status"
              {...crossFadeProps(reduceMotion)}
              className="flex flex-col items-center gap-2 text-success"
            >
              <CheckCircle2 className="size-4" aria-hidden />
              <span className="text-[13px]">Upload complete</span>
            </motion.div>
          ) : phase === "error" ? (
            <motion.div
              key="error"
              role="status"
              {...crossFadeProps(reduceMotion)}
              className="flex flex-col items-center gap-2 text-error"
            >
              <XCircle className="size-4" aria-hidden />
              <span className="text-[13px]">Upload failed</span>
            </motion.div>
          ) : (
            <motion.button
              key="idle"
              type="button"
              {...crossFadeProps(reduceMotion)}
              onClick={() => inputRef.current?.click()}
              aria-label="Upload PDF or TXT files (click to browse or drop files here)"
              className="flex w-full flex-col items-center gap-2 hover:text-foreground"
            >
              <UploadCloud
                className="size-4 text-muted-foreground"
                aria-hidden
              />
              <span className="text-[13px] text-muted-foreground">
                {dragActive ? "Drop to upload" : "Add or drop PDF / TXT files"}
              </span>
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      {/* Outcome of the last batch — persists (unlike the toasts)
          until the next upload starts, so a glance at the sidebar
          confirms what just happened. */}
      {lastResults.length > 0 && (
        <ul
          role="status"
          aria-live="polite"
          aria-label="Upload results"
          className="mt-2 flex flex-col gap-1"
        >
          <AnimatePresence initial={false}>
            {lastResults.map((r) => {
              const failed = r.status === "error";
              return (
                <motion.li
                  key={r.filename}
                  layout={!reduceMotion}
                  initial={reduceMotion ? false : { opacity: 0, y: -4 }}
                  animate={
                    reduceMotion
                      ? undefined
                      : failed
                        ? { opacity: 1, y: 0, x: [0, -3, 3, -3, 0] }
                        : { opacity: 1, y: 0 }
                  }
                  exit={reduceMotion ? undefined : { opacity: 0 }}
                  transition={{ duration: failed ? 0.3 : 0.18, ease: "easeOut" }}
                  className="flex items-center gap-1.5 rounded-sm px-1 py-0.5 text-xs"
                >
                  {/* Icons are decorative (aria-hidden) — this text
                      is the actual accessible status, since a
                      screen reader can't see icon color/shape. */}
                  <span className="sr-only">
                    {failed ? "Failed: " : "Indexed: "}
                  </span>
                  {failed ? (
                    <XCircle
                      className="size-3.5 shrink-0 text-error"
                      aria-hidden
                    />
                  ) : (
                    <CheckCircle2
                      className="size-3.5 shrink-0 text-success"
                      aria-hidden
                    />
                  )}
                  <span className="truncate text-muted-foreground">
                    {r.filename}
                  </span>
                </motion.li>
              );
            })}
          </AnimatePresence>
        </ul>
      )}
    </>
  );
}
