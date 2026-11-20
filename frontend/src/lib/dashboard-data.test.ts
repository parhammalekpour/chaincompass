import { describe, expect, it } from "vitest";
import type { ScoreHistoryItem } from "@/lib/public-api/contracts";
import {
  buildScoreHistoryChartData,
  formatCompactUsd,
  formatCoverage,
  formatPercentShare,
  formatScore,
  formatSignedPercent,
  getScoreHistoryDateRange,
} from "./dashboard-data";

function historyItem(
  date: string,
  score: string,
  isPartial = false,
): ScoreHistoryItem {
  return {
    as_of_date: date,
    score,
    coverage: "0.6",
    is_partial: isPartial,
    confidence_label: "Medium",
  };
}

describe("dashboard data helpers", () => {
  it("builds UTC ranges with exactly the requested number of days", () => {
    const now = new Date("2026-01-01T23:30:00-05:00");
    const oneYear = getScoreHistoryDateRange("1y", now);
    const threeYears = getScoreHistoryDateRange("3y", now);
    const maximum = getScoreHistoryDateRange("max", now);

    expect(oneYear).toEqual({ from: "2025-01-03", to: "2026-01-02" });
    expect(
      (Date.parse(`${threeYears.to}T00:00:00Z`) -
        Date.parse(`${threeYears.from}T00:00:00Z`)) /
        86_400_000 +
        1,
    ).toBe(1095);
    expect(
      (Date.parse(`${maximum.to}T00:00:00Z`) -
        Date.parse(`${maximum.from}T00:00:00Z`)) /
        86_400_000 +
        1,
    ).toBe(3650);
  });

  it("keeps every missing day as a null chart value", () => {
    const data = buildScoreHistoryChartData(
      [
        {
          slug: "btc",
          items: [
            historyItem("2026-01-01", "41.570000"),
            historyItem("2026-01-03", "42.1", true),
          ],
        },
      ],
      { from: "2026-01-01", to: "2026-01-03" },
    );

    expect(data.map((point) => point.date)).toEqual([
      "2026-01-01",
      "2026-01-02",
      "2026-01-03",
    ]);
    expect(data.map((point) => point.btc)).toEqual([41.57, null, 42.1]);
    expect(data[1].eth).toBeNull();
    expect(data[2].btcPartial).toBe(true);
  });

  it("formats decimal strings at the display boundary with Latin digits", () => {
    expect(formatScore("41.570000")).toBe("41.6");
    expect(formatCoverage("0.6000")).toBe("60");
    expect(formatCompactUsd("1250")).toContain("1.25K");
    expect(formatCompactUsd("1250")).toMatch(/\$/);
    expect(formatSignedPercent("-0.1234")).toBe("-12.34%");
    expect(formatPercentShare("0.4579")).toBe("45.79%");
    expect(
      `${formatScore("41.570000")}${formatSignedPercent("-0.1234")}`,
    ).not.toMatch(/[\u0660-\u0669\u06f0-\u06f9]/);
  });
});