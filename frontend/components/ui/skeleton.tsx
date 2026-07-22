import { cn } from "@/lib/utils";

// Loading skeleton — DESIGN.md §13. Uses the design-system skeleton
// tokens with the sanctioned shimmer sweep (which automatically goes
// static under prefers-reduced-motion; see globals.css). Radius is
// overridden per use to match the element being stood in for.
//
// A <Skeleton> only ever exists while something is loading — that's
// its whole purpose — so it's unconditionally an accessible busy
// status region with a (visually hidden) "Loading…" label, rather
// than the silent, unlabeled div it was before. The shimmering bar
// itself carries no information, so it stays out of the way; the
// sr-only text is what a screen reader actually announces.

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      role="status"
      aria-busy="true"
      aria-live="polite"
      className={cn("skeleton-shimmer rounded-md bg-skeleton", className)}
      {...props}
    >
      <span className="sr-only">Loading…</span>
    </div>
  );
}

export { Skeleton };
