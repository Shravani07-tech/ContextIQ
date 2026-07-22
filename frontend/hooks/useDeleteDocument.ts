"use client";

// Single-document delete (DELETE /documents/{filename}) — removes
// just this document's vectors + disk file, leaving the rest of the
// knowledge base untouched. Unlike useDatabase's clearDatabase(),
// this doesn't wipe everything.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { useDocumentMeta } from "@/hooks/useDocumentMeta";
import { api } from "@/lib/api";

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  const { removeMeta } = useDocumentMeta();

  return useMutation({
    mutationFn: (filename: string) => api.deleteDocument(filename),
    onSuccess: (result) => {
      toast.success(`Deleted ${result.filename}`);
      removeMeta(result.filename);
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["status"] });
    },
    onError: (error, filename) => {
      toast.error(`Could not delete ${filename}`, {
        description: error.message,
      });
    },
  });
}
