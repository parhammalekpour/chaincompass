"use client";

import { useQueries } from "@tanstack/react-query";
import { getChainDetail } from "@/lib/public-api/client";
import type { ChainSlug } from "@/lib/public-api/contracts";
import { publicQueryKeys } from "@/lib/public-api/query-keys";

export function usePartialCoverageDetails(slugs: readonly ChainSlug[]) {
  return useQueries({
    queries: slugs.map((slug) => ({
      queryKey: publicQueryKeys.chain(slug),
      queryFn: () => getChainDetail(slug),
    })),
  });
}