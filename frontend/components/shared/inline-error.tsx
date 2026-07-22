// Shared inline error + retry card — the "Couldn't load X" fallback
// used wherever a query can fail without taking the whole page down
// (sidebar document list, document library, model details). Previously
// this soft-error block with its Retry button was copied near-verbatim
// in all three places; one component keeps the wording, styling, and
// keyboard behavior consistent.

import { cn } from "@/lib/utils";

export function InlineError({
  message,
  onRetry,
  className,
}: {
  message: string;
  onRetry: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center gap-2 rounded-lg border border-error/40 bg-error-soft px-3 py-6 text-center",
        className,
      )}
    >
      <p className="text-[13px] text-error">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-sm border border-border bg-secondary px-2 py-1 text-xs transition-colors duration-150 hover:bg-accent"
      >
        Retry
      </button>
    </div>
  );
}
