"use client";

// Top navigation bar — the health dot is live (GET /health); the
// model badge stays static until GET /status is wired in Phase 3B.
// Mobile: the menu button opens the sidebar in a Sheet drawer.

import { Menu } from "lucide-react";

import { Sidebar } from "@/components/sidebar/sidebar";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useHealth } from "@/hooks/useHealth";

export function TopNav() {
  const health = useHealth();

  const status = health.isPending
    ? { dot: "bg-info", label: "Connecting…" }
    : health.isError
      ? { dot: "bg-error", label: "Offline" }
      : health.data.status === "ok"
        ? { dot: "bg-success", label: "Operational" }
        : { dot: "bg-warning", label: "Degraded" };

  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-background px-4">
      <div className="flex items-center gap-3">
        <Sheet>
          {/* Base UI composition: `render` supplies the element,
              children render inside it. */}
          <SheetTrigger
            aria-label="Open sidebar"
            render={
              <button
                type="button"
                className="flex size-8 items-center justify-center rounded-sm text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground md:hidden"
              />
            }
          >
            <Menu className="size-4" aria-hidden />
          </SheetTrigger>
          <SheetContent
            side="left"
            className="w-[280px] border-sidebar-border p-0"
          >
            <SheetTitle className="sr-only">ContextIQ sidebar</SheetTitle>
            <Sidebar />
          </SheetContent>
        </Sheet>
        <span className="text-[13px] font-medium">Chat</span>
      </div>

      <div className="flex items-center gap-3">
        {/* Static until GET /status is wired (Phase 3B). */}
        <span className="rounded-full border border-border bg-secondary px-2 py-0.5 font-mono text-xs text-muted-foreground">
          llama3.2
        </span>
        <span className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex">
          <span
            className={`size-1.5 rounded-full ${status.dot}`}
            aria-hidden
          />
          {status.label}
        </span>
      </div>
    </header>
  );
}
