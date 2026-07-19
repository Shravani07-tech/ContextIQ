// Route-level loading UI (App Router convention): while a page is
// being prepared, the layout-shaped shell skeleton shows instead of
// a blank screen — no flash, no spinner soup.

import { ShellSkeleton } from "@/components/layout/shell-skeleton";

export default function Loading() {
  return <ShellSkeleton />;
}
