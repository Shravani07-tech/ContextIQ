"use client";

// Last-resort boundary: catches errors thrown by the ROOT layout
// itself, where error.tsx can't help. It must render its own <html>
// and <body> (it replaces the layout entirely), so globals.css is
// imported directly for the design tokens.

import "./globals.css";

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en" className="dark">
      <body className="flex min-h-dvh items-center justify-center bg-background p-6 font-sans text-foreground antialiased">
        <div className="flex w-full max-w-sm flex-col items-center gap-3 rounded-lg border border-border bg-card p-8 text-center">
          <h1 className="text-lg font-semibold">ContextIQ crashed</h1>
          <p className="text-[13px] leading-relaxed text-muted-foreground">
            A fatal interface error occurred. Reloading usually fixes it;
            your documents are stored server-side and are not affected.
          </p>
          <button
            type="button"
            onClick={reset}
            className="mt-2 rounded-sm bg-primary px-4 py-2 text-[13px] font-medium text-primary-foreground transition-colors duration-150 hover:bg-primary/90"
          >
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}
