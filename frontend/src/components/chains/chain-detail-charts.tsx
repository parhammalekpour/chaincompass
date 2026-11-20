"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTranslations } from "next-intl";
import type { ChainChartPoint } from "@/lib/chain-detail-data";
import type { ScoreHistoryRange } from "@/lib/dashboard-data";
import { formatCompactUsd, formatScore } from "@/lib/dashboard-data";
import { Button } from "@/components/ui/button";

const ranges: ScoreHistoryRange[] = ["1y", "3y", "max"];

function isChartPoint(value: unknown): value is ChainChartPoint {
  return (
    typeof value === "object" &&
    value !== null &&
    "date" in value &&
    typeof value.date === "string" &&
    "value" in value &&
    (typeof value.value === "number" || value.value === null)
  );
}

function confidenceKey(
  value: string,
): "high" | "medium" | "low" | null {
  switch (value) {
    case "High":
      return "high";
    case "Medium":
      return "medium";
    case "Low":
      return "low";
    default:
      return null;
  }
}

function ChartFigure({
  title,
  accessibleLabel,
  textAlternative,
  data,
  formatValue,
  domain,
  showScoreMeta,
}: {
  title: string;
  accessibleLabel: string;
  textAlternative: string;
  data: ChainChartPoint[];
  formatValue: (value: string) => string;
  domain?: [number, number];
  showScoreMeta: boolean;
}) {
  const dashboardT = useTranslations("dashboard");

  return (
    <figure
      aria-label={accessibleLabel}
      className="rounded-xl border border-border p-4"
    >
      <figcaption className="font-semibold">{title}</figcaption>
      <p className="sr-only">{textAlternative}</p>
      <div className="mt-4 h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
            <CartesianGrid stroke="#94a3b8" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={48} />
            <YAxis
              domain={domain}
              tick={{ fontSize: 11 }}
              tickFormatter={(value: number) => formatValue(String(value))}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                const point = payload?.[0]?.payload;
                if (!active || !isChartPoint(point) || point.value === null) {
                  return null;
                }
                const scoreConfidence =
                  point.confidence && confidenceKey(point.confidence);
                return (
                  <div className="space-y-1 rounded-lg border border-border bg-card p-3 text-sm shadow-md">
                    <p dir="ltr" className="tabular-nums">{String(label)}</p>
                    <p dir="ltr" className="tabular-nums">
                      {formatValue(String(point.value))}
                    </p>
                    {showScoreMeta && scoreConfidence && (
                      <p>
                        {dashboardT("tooltipConfidence")}:{" "}
                        {dashboardT(`confidence.${scoreConfidence}`)}
                      </p>
                    )}
                    {showScoreMeta && point.partial && (
                      <p>{dashboardT("partial")}</p>
                    )}
                  </div>
                );
              }}
            />
            <Line
              type="linear"
              dataKey="value"
              stroke="#0e7490"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

export function ChainDetailCharts({
  scoreData,
  priceData,
  range,
  onRangeChange,
  showScore,
  showPrice,
}: {
  scoreData: ChainChartPoint[];
  priceData: ChainChartPoint[];
  range: ScoreHistoryRange;
  onRangeChange: (range: ScoreHistoryRange) => void;
  showScore: boolean;
  showPrice: boolean;
}) {
  const t = useTranslations("chainDetail");
  const dashboardT = useTranslations("dashboard");

  return (
    <div className="space-y-5">
      {showScore && (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-semibold">{t("historyTitle")}</h3>
            <div
              role="group"
              aria-label={dashboardT("rangeLabel")}
              className="flex gap-2"
            >
              {ranges.map((item) => (
                <Button
                  key={item}
                  size="sm"
                  variant={item === range ? "default" : "outline"}
                  aria-pressed={item === range}
                  onClick={() => onRangeChange(item)}
                >
                  {dashboardT(`ranges.${item}`)}
                </Button>
              ))}
            </div>
          </div>
          <ChartFigure
            title={t("historyTitle")}
            accessibleLabel={t("scoreChartAccessibleLabel")}
            textAlternative={t("scoreChartTextAlternative")}
            data={scoreData}
            formatValue={formatScore}
            domain={[0, 100]}
            showScoreMeta
          />
        </section>
      )}
      {showPrice && (
        <section className="space-y-3">
        <ChartFigure
          title={t("priceHistoryTitle")}
          accessibleLabel={t("priceChartAccessibleLabel")}
          textAlternative={t("priceChartTextAlternative")}
          data={priceData}
          formatValue={formatCompactUsd}
          showScoreMeta={false}
        />
        </section>
      )}
    </div>
  );
}
