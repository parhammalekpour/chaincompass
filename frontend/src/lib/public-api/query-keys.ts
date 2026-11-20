import type { ChainSlug } from "./contracts";

const publicRoot = ["public"] as const;

export const publicQueryKeys = {
  chains: [...publicRoot, "chains"] as const,
  chain: (slug: ChainSlug) => [...publicRoot, "chain", slug] as const,
  scoreHistory: (
    slug: ChainSlug,
    range: { from: string; to: string },
  ) => [...publicRoot, "score-history", slug, range.from, range.to] as const,
};
