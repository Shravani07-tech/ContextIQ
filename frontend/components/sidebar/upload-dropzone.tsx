"use client";

// Upload dropzone — drag & drop plus click-to-browse, with the three
// workflow states rendered in place:
//   idle      -> icon + "Add or drop PDF / TXT files"
//   uploading -> progress bar with byte-level percentage (XHR)
//   indexing  -> spinner (duration depends on the embedding model,
//                so an indeterminate state is the honest one)
// Drag feedback uses the ring-blue border + soft accent tint from
// the design system. A drag-enter/leave counter prevents flicker
// when dragging across child elements.

import { Loader2, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

import { useUpload } from "@/hooks/useUpload";

export function UploadDropzone() {
  const { uploadFiles, phase, progress, isPending } = useUpload();
  const inputRef = useRef<HTMLInputElement>(null);
  const dragCounter = useRef(0);
  const [dragActive, setDragActive] = useState(false);

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    dragCounter.current = 0;
    setDragActive(false);
    if (isPending) return;
    uploadFiles(Array.from(e.dataTransfer.files));
  }

  function onDragEnter(e: React.DragEvent) {
    e.preventDefault();
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

      <button
        type="button"
        disabled={isPending}
        onClick={() => inputRef.current?.click()}
        onDrop={onDrop}
        onDragEnter={onDragEnter}
        onDragLeave={onDragLeave}
        onDragOver={(e) => e.preventDefault()}
        aria-label="Upload PDF or TXT files (click to browse or drop files here)"
        className={`flex flex-col items-center gap-2 rounded-lg border border-dashed p-4 text-center transition-colors duration-150 disabled:cursor-wait ${
          dragActive
            ? "border-ring bg-info-soft"
            : "border-input hover:border-ring hover:bg-sidebar-accent"
        }`}
      >
        {phase === "uploading" ? (
          <div className="w-full">
            <p className="text-[13px] text-muted-foreground">
              Uploading… {progress}%
            </p>
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
          </div>
        ) : phase === "indexing" ? (
          <>
            <Loader2
              className="size-4 animate-spin text-muted-foreground"
              aria-hidden
            />
            <span className="text-[13px] text-muted-foreground">
              Indexing — chunking &amp; embedding…
            </span>
          </>
        ) : (
          <>
            <UploadCloud
              className="size-4 text-muted-foreground"
              aria-hidden
            />
            <span className="text-[13px] text-muted-foreground">
              {dragActive ? "Drop to upload" : "Add or drop PDF / TXT files"}
            </span>
          </>
        )}
      </button>
    </>
  );
}
