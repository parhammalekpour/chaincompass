import { describe, expect, it } from "vitest";
import chainsFixture from "@/test/fixtures/chains.json";
import type { ChainSummary } from "@/lib/public-api/contracts";
import {
  defaultScreenerState,
  filterAndSortChains,
  parseScreenerParams,
  serializeScreenerParams,
} from "./chains-screener";

const chains = chainsFixture.chains as ChainSummary[];

describe("chains screener helpers", () => {
  it("sanitizes unknown sort and regime query values", () => {
    const state = parseScreenerParams("?sort=evil&regime=xyz");

    expect(state).toEqual(defaultScreenerState);
    expect(parseScreenerParams(`?${serializeScreenerParams(state)}`)).toEqual(
      state,
    );
  });

  it("keeps null values last in either sort direction", () => {
    const chainsWithNull = chains.map((chain, index) =>
      index === 0 ? { ...chain, score: null } : chain,
    );
    const ascending = filterAndSortChains(chainsWithNull, {
      ...defaultScreenerState,
      sort: "score",
    });
    const descending = filterAndSortChains(chainsWithNull, {
      ...defaultScreenerState,
      sort: "score",
      direction: "desc",
    });

    expect(ascending.map((chain) => chain.slug)).toEqual([
      "eth",
      "sol",
      "bnb",
      "btc",
    ]);
    expect(descending.map((chain) => chain.slug)).toEqual([
      "bnb",
      "sol",
      "eth",
      "btc",
    ]);
    expect(ascending[ascending.length - 1]?.score).toBeNull();
    expect(descending[descending.length - 1]?.score).toBeNull();
  });

  it("applies regime, confidence, and risk-flag filters together", () => {
    const filtered = filterAndSortChains(chains, {
      ...defaultScreenerState,
      regime: "downtrend",
      confidence: "High",
      hasRiskFlags: true,
    });

    expect(filtered.map((chain) => chain.slug)).toEqual(["eth"]);
  });
});