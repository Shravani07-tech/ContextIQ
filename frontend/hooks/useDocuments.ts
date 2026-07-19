"use client";

// Indexed document list. Cached under ["documents"] — upload and
// clear-database mutations invalidate this key, so every consumer
// (sidebar list, right-panel stats) refreshes automatically.

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export function useDocuments() {
  return useQuery({
    queryKey: ["documents"],
    queryFn: api.documents,
    select: (data) => data.documents,
  });
}
