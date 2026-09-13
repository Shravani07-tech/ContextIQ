import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Collection, CollectionCreate, CollectionUpdate } from "@/lib/types";

// Module-level global state for active collection selection across UI components
let globalActiveCollectionId: string | null = null;
const listeners = new Set<(id: string | null) => void>();

export function useActiveCollection() {
  const [activeId, setActiveIdState] = useState<string | null>(globalActiveCollectionId);

  useEffect(() => {
    const handler = (id: string | null) => setActiveIdState(id);
    listeners.add(handler);
    return () => {
      listeners.delete(handler);
    };
  }, []);

  const setActiveCollectionId = (id: string | null) => {
    globalActiveCollectionId = id;
    listeners.forEach((fn) => fn(id));
  };

  return [activeId, setActiveCollectionId] as const;
}

export function useCollections() {
  return useQuery({
    queryKey: ["collections"],
    queryFn: async () => {
      const res = await api.collections();
      return res.collections;
    },
  });
}

export function useCreateCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CollectionCreate) => api.createCollection(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["collections"] });
    },
  });
}

export function useUpdateCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: CollectionUpdate }) =>
      api.updateCollection(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["collections"] });
    },
  });
}

export function useDeleteCollection() {
  const qc = useQueryClient();
  const [_, setActiveId] = useActiveCollection();

  return useMutation({
    mutationFn: (id: string) => api.deleteCollection(id),
    onSuccess: (_, deletedId) => {
      qc.invalidateQueries({ queryKey: ["collections"] });
      qc.invalidateQueries({ queryKey: ["documents"] });
      if (globalActiveCollectionId === deletedId) {
        setActiveId(null);
      }
    },
  });
}
