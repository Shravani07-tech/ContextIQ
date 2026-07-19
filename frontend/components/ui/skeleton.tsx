import { cn } from "@/lib/utils";

// Loading skeleton — DESIGN.md §13. Uses the design-system skeleton
// tokens with the sanctioned shimmer sweep (which automatically goes
// static under prefers-reduced-motion; see globals.css). Radius is
// overridden per use to match the element being stood in for.

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("skeleton-shimmer rounded-md bg-skeleton", className)}
      {...props}
    />
  );
}

export { Skeleton };
