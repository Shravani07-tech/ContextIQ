"use client";

// Clear-database mutation (DELETE /database). Destructive, so the
// UI gates it behind a confirmation toast; on success every cached
// document-derived view refreshes.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";

export function useClearDatabase() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: api.clearDatabase,
    onSuccess: () => {
      toast.success("Database cleared", {
        description: "All vectors removed. Files on disk are kept.",
      });
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (error) => {
      toast.error("Could not clear the database", {
        description: error.message,
      });
    },
  });
}
