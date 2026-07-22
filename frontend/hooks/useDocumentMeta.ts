"use client";

// Client-side cache of per-document size/chunk-count/upload-time,
// captured at the moment of upload (see useUpload.ts) and persisted
// to localStorage so it survives a refresh. This exists because the
// backend only stores `filename` per chunk — see the comment on
// DocumentMeta in lib/types.ts for why that isn't being extended.
//
// Not a TanStack Query resource: this is local device state, not
// server state, so a plain localStorage-backed React state hook is
// the right tool rather than forcing it through the query cache.

import { useCallback, useEffect, useState } from "react";

import type { DocumentMeta } from "@/lib/types";

const STORAGE_KEY = "contextiq.documentMeta.v1";

type MetaRecord = Record<string, DocumentMeta>;

function readStorage(): MetaRecord {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as MetaRecord) : {};
  } catch {
    return {};
  }
}

function writeStorage(record: MetaRecord): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(record));
  } catch {
    // Storage full/blocked — metadata just won't persist this time.
  }
}

export function useDocumentMeta() {
  // Lazy-initialized from storage once per mount; not read again on
  // every render (avoids re-parsing JSON on each call to the hook).
  const [meta, setMeta] = useState<MetaRecord>(() =>
    typeof window === "undefined" ? {} : readStorage(),
  );

  // Re-sync if another tab updates the same key (e.g. two tabs
  // uploading to the same local backend).
  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key === STORAGE_KEY) setMeta(readStorage());
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const recordUpload = useCallback(
    (filename: string, data: { sizeBytes: number; chunks: number }) => {
      setMeta((prev) => {
        const next = {
          ...prev,
          [filename]: { ...data, uploadedAt: Date.now() },
        };
        writeStorage(next);
        return next;
      });
    },
    [],
  );

  const removeMeta = useCallback((filename: string) => {
    setMeta((prev) => {
      if (!(filename in prev)) return prev;
      const next = { ...prev };
      delete next[filename];
      writeStorage(next);
      return next;
    });
  }, []);

  // Used when the WHOLE database is cleared (useDatabase.ts): without
  // this, a same-named file re-added later through a different path
  // (e.g. the CLI) could show this browser's stale leftover size/
  // chunk/time from before the clear.
  const clearAllMeta = useCallback(() => {
    setMeta({});
    writeStorage({});
  }, []);

  return { meta, recordUpload, removeMeta, clearAllMeta };
}
