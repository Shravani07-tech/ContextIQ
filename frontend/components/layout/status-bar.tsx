"use client";

// Bottom status bar — app version and LIVE backend status from
// GET /health: green connected, amber degraded (API up but a
// dependency down), red offline.

import { useHealth } from "@/hooks/useHealth";
import { healthDisplay } from "@/lib/health";
import { APP_VERSION } from "@/lib/version";

export function StatusBar() {
  const health = useHealth();

  const state = healthDisplay(health, {
    connecting: "backend: connecting…",
    offline: "backend: offline",
    ok: "backend: connected",
    degraded: "backend: degraded",
  });

  return (
    <footer className="flex h-8 shrink-0 items-center justify-between border-t border-border bg-background px-4 font-mono text-xs text-muted-foreground">
      <div className="flex items-center gap-4">
        <span>ContextIQ v{APP_VERSION}</span>
      </div>
      <span className="flex items-center gap-1.5">
        <span className={`size-1.5 rounded-full ${state.dot}`} aria-hidden />
        {state.label}
      </span>
    </footer>
  );
}
