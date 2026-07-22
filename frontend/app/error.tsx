"use client";

// Route-level error boundary (App Router convention). Catches render
// and lifecycle errors below the root layout, so a crash shows a
// designed recovery screen instead of a white page. The raw error is
// logged for diagnosis but never rendered — same policy as the API.

import { AlertTriangle, RotateCcw } from "lucide-react";
import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("ContextIQ UI error:", error);
  }, [error]);

  return (
    <main className="flex min-h-dvh items-center justify-center bg-background p-6 text-foreground">
      <div className="flex w-full max-w-sm flex-col items-center gap-3 rounded-lg border border-border bg-card p-8 text-center">
        <div className="flex size-10 items-center justify-center rounded-md bg-error-soft">
          <AlertTriangle className="size-5 text-error" aria-hidden />
        </div>
        <h1 className="text-lg font-semibold">Something went wrong</h1>
        <p className="text-[13px] leading-relaxed text-muted-foreground">
          The interface hit an unexpected error. Your documents and
          conversation are safe — try again.
        </p>
        <button
          type="button"
          onClick={reset}
          className="mt-2 flex items-center gap-2 rounded-sm bg-primary px-4 py-2 text-[13px] font-medium text-primary-foreground transition-colors duration-150 hover:bg-primary/90"
        >
          <RotateCcw className="size-4" aria-hidden />
          Try again
        </button>
      </div>
    </main>
  );
}
