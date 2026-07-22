"use client";

// Knowledge-base status + pipeline settings (GET /status): vector
// count, document count, chunking config, top-K, and the ACTUAL
// model names the backend is running — replacing every hardcoded
// status value in the UI. Cached under ["status"]; upload and
// clear-database mutations invalidate it so the counts stay honest.

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export function useStatus() {
  return useQuery({
    queryKey: ["status"],
    queryFn: api.status,
  });
}
