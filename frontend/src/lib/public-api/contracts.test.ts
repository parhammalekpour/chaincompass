import chainsFixture from "@/test/fixtures/chains.json";
import chainDetailFixture from "@/test/fixtures/btc-chain-detail.json";
import nullScoreFixture from "@/test/fixtures/chains-null-score.synthetic.json";
import methodologyFixture from "@/test/fixtures/methodology-detail.json";
import priceSeriesFixture from "@/test/fixtures/btc-price-series.json";
import regimesFixture from "@/test/fixtures/btc-regimes.json";
import scoreHistoryFixture from "@/test/fixtures/btc-score-history-30d.json";
import scenariosFixture from "@/test/fixtures/btc-scenarios.json";
import fundamentalReportFixture from "@/test/fixtures/fundamental-report.json";
import { describe, expect, it } from "vitest";
import {
  chainsResponseSchema,
  chainDetailResponseSchema,
  methodologyResponseSchema,
  regimesResponseSchema,
  scoreHistoryResponseSchema,
  scenariosResponseSchema,
  fundamentalReportResponseSchema,
  seriesResponseSchema,
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

  it("parses the captured chain detail including pillar availability", () => {
    const response = chainDetailResponseSchema.parse(chainDetailFixture);

    expect(response.score?.pillars.capital?.available).toBe(false);
    expect(response.last_full_coverage?.as_of_date).toBe("2026-11-18");
  });

  it("parses captured regime, price series, and scenario responses", () => {
    expect(regimesResponseSchema.parse(regimesFixture).segments).toHaveLength(3);
    expect(seriesResponseSchema.parse(priceSeriesFixture).meta.metric).toBe(
      "price_close_usd",
    );
    expect(
      scenariosResponseSchema.parse(scenariosFixture).horizons[2]?.low_sample,
    ).toBe(true);
  });

  it("parses methodology fields used for pillar weights and source names", () => {
    const response = methodologyResponseSchema.parse(methodologyFixture);

    expect(response.pillars[0]?.weight).toBe(30);
    expect(response.sources[0]?.name).toBe("Binance");
  });

  it("parses the fundamental report and tolerates unknown fields", () => {
    const response = fundamentalReportResponseSchema.parse({
      ...fundamentalReportFixture,
      extra_field: "ignored by report rendering",
      health: { ...fundamentalReportFixture.health, future_field: true },
    });

    expect(response.health.score).toBe("55.25");
    expect(response.indicators).toHaveLength(11);
    expect(response.data_gaps[3]?.status).toBe("not_available_free");
  });

  it("accepts nullable report history and regime fields", () => {
    const response = fundamentalReportResponseSchema.parse({
      ...fundamentalReportFixture,
      health: {
        ...fundamentalReportFixture.health,
        score_30d_ago: null,
        score_90d_ago: null,
        change_30d: null,
        change_90d: null,
      },
      regime: {
        regime: null,
        vol_state: null,
        since_date: null,
        days_in_regime: null,
        history_gap: true,
      },
    });

    expect(response.health.change_30d).toBeNull();
    expect(response.regime.since_date).toBeNull();
  });

  it("rejects unknown indicator statuses and malformed reports", () => {
    const unknownStatus = {
      ...fundamentalReportFixture,
      indicators: fundamentalReportFixture.indicators.map((indicator, index) =>
        index === 0 ? { ...indicator, status: "unverified" } : indicator,
      ),
    };

    expect(fundamentalReportResponseSchema.safeParse(unknownStatus).success).toBe(
      false,
    );
    expect(
      fundamentalReportResponseSchema.safeParse({
        ...fundamentalReportFixture,
        health: undefined,
      }).success,
    ).toBe(false);
  });
});
