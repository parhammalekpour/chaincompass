"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartDirectionWrapper } from "./chart-direction-wrapper";
import type {
  ScoreHistoryChartPoint,
  ScoreHistoryRange,
} from "@/lib/dashboard-data";
import type { ChainSlug } from "@/lib/public-api/contracts";
import { Button } from "@/components/ui/button";

type ChartSeries = {
  slug: ChainSlug;
  color: string;
  dash: string;
};

const chartSeries: readonly ChartSeries[] = [
  { slug: "btc", color: "#14b8a6", dash: "" },
  { slug: "eth", color: "#6366f1", dash: "8 3" },
  { slug: "sol", color: "#f59e0b", dash: "3 3" },
  { slug: "bnb", color: "#8b5cf6", dash: "10 3 2 3" },
];

type TooltipEntry = {
  dataKey?: string | number;
  value?: unknown;
  payload?: unknown;
};

type ScoreTooltipProps = {
  active?: boolean;
  label?: string;
  payload?: TooltipEntry[];
};

function isChartPoint(value: unknown): value is ScoreHistoryChartPoint {
  return typeof value === "object" && value !== null && "date" in value;
}

function confidenceFor(
  point: ScoreHistoryChartPoint,
  slug: ChainSlug,
): string | undefined {
  switch (slug) {
    case "btc":
      return point.btcConfidence;
    case "eth":
      return point.ethConfidence;
    case "sol":
      return point.solConfidence;
    case "bnb":
      return point.bnbConfidence;
  }
}

function partialFor(point: ScoreHistoryChartPoint, slug: ChainSlug): boolean {
  switch (slug) {
    case "btc":
      return point.btcPartial ?? false;
    case "eth":
      return point.ethPartial ?? false;
    case "sol":
      return point.solPartial ?? false;
    case "bnb":
      return point.bnbPartial ?? false;
  }
}

function ScoreTooltip({ active, payload, label }: ScoreTooltipProps) {
  const t = useTranslations("dashboard");
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded-lg border border-border bg-popover p-3 text-xs text-popover-foreground shadow-lg">
      <p dir="ltr" className="mb-2 tabular-nums font-medium">
        {label}
      </p>
      <ul className="space-y-1.5">
        {payload.map((entry) => {
          if (
            typeof entry.dataKey !== "string" ||
            typeof entry.value !== "number" ||
            !isChartPoint(entry.payload)
          ) {
            return null;
          }
          const slug = entry.dataKey as ChainSlug;
          const confidence = confidenceFor(entry.payload, slug);
          return (
            <li key={slug} className="space-y-0.5">
              <p>
                {t(`chainNames.${slug}`)}:{" "}
                {t("tooltipScore")}{" "}
                {new Intl.NumberFormat("en-US", {
                  minimumFractionDigits: 1,
                  maximumFractionDigits: 1,
                }).format(entry.value)}{" "}
                /100
              </p>
              {confidence && (
                <p className="text-muted">
                  {t("tooltipConfidence")}: {t(`confidence.${confidence.toLowerCase()}`)}
                </p>
              )}
              {partialFor(entry.payload, slug) && (
                <p className="text-muted">{t("partial")}</p>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function ScoreHistoryChart({
  data,
  range,
  onRangeChange,
}: {
  data: ScoreHistoryChartPoint[];
  range: ScoreHistoryRange;
  onRangeChange: (range: ScoreHistoryRange) => void;
}) {
  const t = useTranslations("dashboard");
  const [hidden, setHidden] = useState<ReadonlySet<ChainSlug>>(new Set());
  const hasScores = data.some((point) =>
    chartSeries.some((series) => point[series.slug] !== null),
  );

  const toggleSeries = (slug: ChainSlug) => {
    setHidden((current) => {
      const next = new Set(current);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  };

  return (
    <section className="space-y-3 rounded-xl border border-border bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{t("chartTitle")}</h2>
        <div
          dir="ltr"
          className="flex gap-1"
          role="group"
          aria-label={t("rangeLabel")}
        >
          {(["1y", "3y", "max"] as const).map((value) => (
            <Button
              key={value}
              variant={range === value ? "secondary" : "outline"}
              size="sm"
              aria-pressed={range === value}
              onClick={() => onRangeChange(value)}
            >
              {t(`ranges.${value}`)}
            </Button>
          ))}
        </div>
      </div>
      <ChartDirectionWrapper className="space-y-3">
        <div className="flex flex-wrap gap-2">
          {chartSeries.map((series) => {
            const name = t(`chainNames.${series.slug}`);
            return (
              <Button
                key={series.slug}
                variant={hidden.has(series.slug) ? "outline" : "secondary"}
                size="sm"
                aria-pressed={!hidden.has(series.slug)}
                onClick={() => toggleSeries(series.slug)}
                className="gap-2"
              >
                <span
                  aria-hidden="true"
                  className="inline-block w-5 border-t-2"
                  style={{
                    borderColor: series.color,
                    borderStyle: series.dash ? "dashed" : "solid",
                  }}
                />
                {name}
              </Button>
            );
          })}
        </div>
        <p className="sr-only">{t("chartTextAlternative")}</p>
        {hasScores ? (
          <div aria-label={t("chartAccessibleLabel")} role="img">
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "var(--muted)", fontSize: 11 }}
                  tickFormatter={(date: string) => date.slice(0, 7)}
                  minTickGap={30}
                />
                <YAxis
                  domain={[0, 100]}
                  ticks={[0, 25, 50, 75, 100]}
                  tick={{ fill: "var(--muted)", fontSize: 11 }}
                />
                <Tooltip content={<ScoreTooltip />} />
                {chartSeries.map((series) =>
                  hidden.has(series.slug) ? null : (
                    <Line
                      key={series.slug}
                      type="linear"
                      dataKey={series.slug}
                      name={t(`chainNames.${series.slug}`)}
                      stroke={series.color}
                      strokeDasharray={series.dash}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4 }}
                      connectNulls={false}
                      isAnimationActive={false}
                    />
                  ),
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="flex h-80 items-center justify-center rounded-lg border border-dashed border-border text-sm text-muted">
            {t("noHistory")}
          </p>
        )}
      </ChartDirectionWrapper>
      <p className="text-sm text-muted">{t("chartCaveat")}</p>
    </section>
  );
}