"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { api } from "./api";

export function useApi<T>(path: string | null) {
  const queryClient = useQueryClient();

  const query = useQuery<T, Error>({
    queryKey: ["api", path],
    queryFn: () => {
      if (!path) throw new Error("Path is null");
      return api<T>(path);
    },
    enabled: Boolean(path),
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  const reload = useCallback(async () => {
    if (!path) return;
    await query.refetch();
  }, [path, query]);

  const setData = useCallback(
    (updater: T | null | ((prev: T | null) => T | null)) => {
      if (!path) return;
      queryClient.setQueryData(["api", path], updater);
    },
    [path, queryClient]
  );

  return {
    data: query.data ?? null,
    error: query.error ?? null,
    loading: query.isLoading,
    reload,
    setData,
  };
}

