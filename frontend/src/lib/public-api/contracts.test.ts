import chainsFixture from "@/test/fixtures/chains.json";
import nullScoreFixture from "@/test/fixtures/chains-null-score.synthetic.json";
import scoreHistoryFixture from "@/test/fixtures/btc-score-history-30d.json";
import { describe, expect, it } from "vitest";
import {
  chainsResponseSchema,
  scoreHistoryResponseSchema,
} from "./contracts";

describe("public API contracts", () => {
  it("parses the captured public chains response", () => {
    const response = chainsResponseSchema.parse(chainsFixture);

    expect(response.chains).toHaveLength(4);
    expect(response.chains[0]?.score?.value).toBe("41.57");
    expect(response.chains[0]?.price.close_usd).toBe("61986.730000000000");
  });

  it("parses the captured BTC score history", () => {
    const response = scoreHistoryResponseSchema.parse(scoreHistoryFixture);

    expect(response.chain).toBe("btc");
    expect(response.items).toHaveLength(30);
    expect(response.items[0]?.as_of_date).toBe("2026-10-21");
  });

  it("accepts the explicitly synthetic null-score chain response", () => {
    const response = chainsResponseSchema.parse(nullScoreFixture);

    expect(response.chains[0]?.score).toBeNull();
    expect(response.chains[0]?.regime).toBeNull();
  });
});
