"use client";

// Backend health, polled every 30s so the status indicators stay
// honest without hammering a local server. `isError` here means the
// API itself is unreachable (distinct from a reachable API reporting
// a degraded dependency).

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
    retry: 1,
  });
}
