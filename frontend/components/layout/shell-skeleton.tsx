// Shell skeleton — the loading stand-in for the whole app shell,
// used by app/loading.tsx during route transitions. Every block
// mirrors the real component it stands in for (DESIGN.md §13:
// skeletons are layout-shaped, radius matches the element).

import { Skeleton } from "@/components/ui/skeleton";

function SidebarSkeleton() {
  return (
    <div className="flex h-full w-[280px] flex-col gap-6 border-r border-sidebar-border bg-sidebar p-4">
      {/* Brand lockup */}
      <div className="flex items-start gap-3">
        <Skeleton className="size-[34px] rounded-md" />
        <div className="flex-1 space-y-1.5">
          <Skeleton className="h-4 w-24 rounded-sm" />
          <Skeleton className="h-3 w-40 rounded-sm" />
        </div>
      </div>
      {/* Upload dropzone */}
      <Skeleton className="h-24 rounded-lg" />
      {/* Document rows */}
      <div className="space-y-2">
        <Skeleton className="h-3 w-28 rounded-sm" />
        <Skeleton className="h-7 w-full rounded-md" />
        <Skeleton className="h-7 w-full rounded-md" />
        <Skeleton className="h-7 w-3/4 rounded-md" />
      </div>
      {/* Status card */}
      <Skeleton className="h-20 rounded-lg" />
    </div>
  );
}

function ChatSkeleton() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-end gap-4 px-4 py-8">
      {/* A short fake conversation: user right, assistant left. */}
      <Skeleton className="ml-auto h-12 w-3/5 rounded-lg" />
      <div className="space-y-2">
        <Skeleton className="h-4 w-full rounded-sm" />
        <Skeleton className="h-4 w-11/12 rounded-sm" />
        <Skeleton className="h-4 w-4/5 rounded-sm" />
      </div>
      <Skeleton className="ml-auto h-10 w-2/5 rounded-lg" />
      {/* Input bar */}
      <Skeleton className="mt-4 h-12 w-full rounded-lg" />
    </div>
  );
}

export function ShellSkeleton() {
  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      <div className="hidden md:block">
        <SidebarSkeleton />
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top nav */}
        <div className="flex h-12 shrink-0 items-center justify-between border-b border-border px-4">
          <Skeleton className="h-4 w-16 rounded-sm" />
          <Skeleton className="h-5 w-24 rounded-full" />
        </div>
        <ChatSkeleton />
        {/* Status bar */}
        <div className="flex h-8 shrink-0 items-center justify-between border-t border-border px-4">
          <Skeleton className="h-3 w-40 rounded-sm" />
          <Skeleton className="h-3 w-32 rounded-sm" />
        </div>
      </div>
    </div>
  );
}
