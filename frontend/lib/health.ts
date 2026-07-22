// Shared mapping from a useHealth() query result to a {dot, label}
// pair — used by both the top-nav indicator and the bottom status
// bar, which previously duplicated this exact 4-branch logic.

import type { UseQueryResult } from "@tanstack/react-query";

import type { HealthResponse } from "@/lib/types";

export interface HealthDisplay {
  dot: string;
  label: string;
}

export function healthDisplay(
  health: UseQueryResult<HealthResponse, Error>,
  labels: { connecting: string; offline: string; ok: string; degraded: string },
): HealthDisplay {
  if (health.isPending) return { dot: "bg-info", label: labels.connecting };
  if (health.isError) return { dot: "bg-error", label: labels.offline };
  if (health.data.status === "ok") return { dot: "bg-success", label: labels.ok };
  return { dot: "bg-warning", label: labels.degraded };
}
