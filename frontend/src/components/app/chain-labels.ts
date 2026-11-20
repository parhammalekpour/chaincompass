import type { ChainSlug } from "@/lib/public-api/contracts";

export const chainNameKeys: Record<
  ChainSlug,
  "chainNames.btc" | "chainNames.eth" | "chainNames.sol" | "chainNames.bnb"
> = {
  btc: "chainNames.btc",
  eth: "chainNames.eth",
  sol: "chainNames.sol",
  bnb: "chainNames.bnb",
};