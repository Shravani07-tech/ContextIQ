// Shared empty-state card: icon + title + muted description, in the
// bordered-card treatment used across sidebar and layout panels.
// Consolidates what was previously two byte-identical copies (the
// sidebar's "No documents yet" and the right panel's "No sources
// yet") into one component — same markup, same classes, no visual
// change, just one place to maintain it.

import type { LucideIcon } from "lucide-react";

export function EmptyPanelState({
  icon: Icon,
  title,
  description,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-5 text-center">
      <Icon className="size-4 text-muted-foreground" aria-hidden />
      <p className="text-[13px] text-muted-foreground">{title}</p>
      <p className="text-xs text-muted-foreground/70">{description}</p>
    </div>
  );
}
