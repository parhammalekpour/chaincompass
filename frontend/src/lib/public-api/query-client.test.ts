import { describe, expect, it } from "vitest";
import { ApiError } from "./client";
import {
  createPublicQueryClient,
  PUBLIC_QUERY_GC_TIME,
  PUBLIC_QUERY_STALE_TIME,
  shouldRetryPublicQuery,
} from "./query-client";

describe("public query defaults", () => {
  it("matches the public API cache window and disables focus refetch", () => {
    const queries = createPublicQueryClient().getDefaultOptions().queries;

    expect(queries?.staleTime).toBe(PUBLIC_QUERY_STALE_TIME);
    expect(queries?.staleTime).toBe(5 * 60 * 1000);
    expect(queries?.gcTime).toBe(PUBLIC_QUERY_GC_TIME);
    expect(queries?.gcTime).toBe(30 * 60 * 1000);
    expect(queries?.refetchOnWindowFocus).toBe(false);
  });

  it("retries once except for client errors", () => {
    expect(
      shouldRetryPublicQuery(0, new ApiError("validation_error", 422)),
    ).toBe(false);
    expect(shouldRetryPublicQuery(0, new ApiError("unknown", 500))).toBe(true);
    expect(shouldRetryPublicQuery(1, new ApiError("unknown", 500))).toBe(false);
  });
});
