"use client";

// Indexed document list and metadata operations.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

export function useDocuments(params?: { collection_id?: string; tag?: string }) {
  return useQuery({
    queryKey: ["documents", params?.collection_id ?? "all", params?.tag ?? "all"],
    queryFn: () => api.documents(params),
    select: (data) => data.documents,
  });
}

export function useDetailedDocuments(params?: { collection_id?: string; tag?: string }) {
  return useQuery({
    queryKey: ["detailed-documents", params?.collection_id ?? "all", params?.tag ?? "all"],
    queryFn: async () => {
      const res = await api.detailedDocuments(params);
      return res.documents;
    },
  });
}

export function useMoveDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ filename, collectionId }: { filename: string; collectionId: string | null }) =>
      api.moveDocument(filename, collectionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["detailed-documents"] });
      qc.invalidateQueries({ queryKey: ["collections"] });
    },
  });
}

export function useAddTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ filename, tag }: { filename: string; tag: string }) =>
      api.addTag(filename, tag),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["detailed-documents"] });
      qc.invalidateQueries({ queryKey: ["tags"] });
    },
  });
}

export function useRemoveTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ filename, tag }: { filename: string; tag: string }) =>
      api.removeTag(filename, tag),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["detailed-documents"] });
      qc.invalidateQueries({ queryKey: ["tags"] });
    },
  });
}

export function useTags() {
  return useQuery({
    queryKey: ["tags"],
    queryFn: async () => {
      const res = await api.tags();
      return res.tags;
    },
  });
}
