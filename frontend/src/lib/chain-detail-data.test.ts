import regimesFixture from "@/test/fixtures/btc-regimes.json";
import scoreHistoryFixture from "@/test/fixtures/btc-score-history-30d.json";
import priceSeriesFixture from "@/test/fixtures/btc-price-series.json";
import { describe, expect, it } from "vitest";
import { regimesResponseSchema, scoreHistoryResponseSchema, seriesResponseSchema } from "./public-api/contracts";
import {
  buildChainScoreHistoryData,
  buildPriceSeriesData,
  buildRegimeTimeline,
} from "./chain-detail-data";

describe("chain detail data builders", () => {
  it("preserves missing score and price dates as null gaps", () => {
    const scoreHistory = scoreHistoryResponseSchema.parse(scoreHistoryFixture);
    const scoreData = buildChainScoreHistoryData(
      [scoreHistory.items[0]!, scoreHistory.items[2]!],
      { from: "2026-10-21", to: "2026-10-23" },
    );
    const series = seriesResponseSchema.parse(priceSeriesFixture);
    const priceData = buildPriceSeriesData([
      series.points[0]!,
      { date: "2025-11-22", value: series.points[1]!.value },
    ]);

    expect(scoreData.map((point) => point.value)).toEqual([
      Number(scoreHistory.items[0]?.score),
      null,
      Number(scoreHistory.items[2]?.score),
    ]);
    expect(scoreData[0]?.confidence).toBe(scoreHistory.items[0]?.confidence_label);
    expect(scoreData[0]?.partial).toBe(scoreHistory.items[0]?.is_partial);
    expect(priceData.map((point) => point.value)).toEqual([
      Number(series.points[0]?.value),
      null,
      Number(series.points[1]?.value),
    ]);
  });

  it("orders regime segments and merges only contiguous runs of the same label", () => {
    const regimes = regimesResponseSchema.parse(regimesFixture);
    const [first, second, last] = regimes.segments;
    expect(first && second && last).toBeTruthy();

    const timeline = buildRegimeTimeline([
      last!,
      { ...second!, regime: first!.regime, start_date: "2026-05-08", end_date: "2026-05-09", days: 2 },
      { ...first!, start_date: "2026-05-06", end_date: "2026-05-07", days: 2 },
      {
        ...second!,
        regime: first!.regime,
        start_date: "2026-05-10",
        end_date: "2026-05-11",
        days: 2,
      },
    ]);

    expect(timeline.map(({ start_date, end_date, days }) => ({
      start_date,
      end_date,
      days,
    }))).toEqual([
      { start_date: "2026-05-06", end_date: "2026-05-11", days: 6 },
      { start_date: "2026-11-16", end_date: "2026-11-19", days: 4 },
    ]);
  });
});
