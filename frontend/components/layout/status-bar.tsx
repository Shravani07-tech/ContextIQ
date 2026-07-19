"use client";

// Bottom status bar — version, git branch, and LIVE backend status
// from GET /health: green connected, amber degraded (API up but a
// dependency down), red offline. Layout unchanged from Phase 2.

import { GitBranch } from "lucide-react";

import { useHealth } from "@/hooks/useHealth";

const VERSION = "v1.5.0";
const BRANCH = "react-migration";

export function StatusBar() {
  const health = useHealth();

  const state = health.isPending
    ? { dot: "bg-info", label: "backend: connecting…" }
    : health.isError
      ? { dot: "bg-error", label: "backend: offline" }
      : health.data.status === "ok"
        ? { dot: "bg-success", label: "backend: connected" }
        : { dot: "bg-warning", label: "backend: degraded" };

  return (
    <footer className="flex h-8 shrink-0 items-center justify-between border-t border-border bg-background px-4 font-mono text-xs text-muted-foreground">
      <div className="flex items-center gap-4">
        <span>ContextIQ {VERSION}</span>
        {/* Branch is nice-to-know — hidden on phones to keep the bar
            from truncating awkwardly at narrow widths. */}
        <span className="hidden items-center gap-1.5 sm:flex">
          <GitBranch className="size-3" aria-hidden />
          {BRANCH}
        </span>
      </div>
      <span className="flex items-center gap-1.5">
        <span className={`size-1.5 rounded-full ${state.dot}`} aria-hidden />
        {state.label}
      </span>
    </footer>
  );
}
