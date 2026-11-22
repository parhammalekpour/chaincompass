import { useQuery } from "@tanstack/react-query";
import { getFundamentalReport } from "@/lib/public-api/client";
import type { ChainSlug } from "@/lib/public-api/contracts";
import { publicQueryKeys } from "@/lib/public-api/query-keys";

export function useFundamentalReport(slug: ChainSlug) {
  return useQuery({
    queryKey: publicQueryKeys.fundamentalReport(slug),
    queryFn: () => getFundamentalReport(slug),
  });
}
