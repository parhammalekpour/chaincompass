import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./client";

export const PUBLIC_QUERY_STALE_TIME = 5 * 60 * 1000;
export const PUBLIC_QUERY_GC_TIME = 30 * 60 * 1000;

export function shouldRetryPublicQuery(
  failureCount: number,
  error: unknown,
): boolean {
  if (
    error instanceof ApiError &&
    error.status >= 400 &&
    error.status < 500
  ) {
    return false;
  }
  return failureCount < 1;
}

export function createPublicQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: PUBLIC_QUERY_STALE_TIME,
        gcTime: PUBLIC_QUERY_GC_TIME,
        retry: shouldRetryPublicQuery,
        refetchOnWindowFocus: false,
      },
    },
  });
}
