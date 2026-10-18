// Small status pill shared by the analysis views (timeline certainty,
// evidence ratings, graph relationship status). Tones map onto the
// semantic tokens in globals.css so contrast is handled once, there.

import { cn } from "@/lib/utils";

export type Tone = "success" | "warning" | "error" | "info" | "neutral";

const TONES: Record<Tone, string> = {
  success: "border-success/30 bg-success-soft text-success",
  warning: "border-warning/30 bg-warning-soft text-warning",
  error: "border-error/30 bg-error-soft text-error",
  info: "border-info/30 bg-info-soft text-info",
  neutral: "border-border bg-secondary text-muted-foreground",
};

export function ToneBadge({
  tone,
  children,
  title,
  className,
}: {
  tone: Tone;
  children: React.ReactNode;
  title?: string;
  className?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-tight",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
