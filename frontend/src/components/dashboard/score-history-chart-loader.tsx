"use client";

import dynamic from "next/dynamic";
import { useQueries } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { getScoreHistory } from "@/lib/public-api/client";
import { publicQueryKeys } from "@/lib/public-api/query-keys";
import { PublicApiErrorState } from "@/components/states/public-api-error-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  buildScoreHistoryChartData,
  getScoreHistoryDateRange,
  type ScoreHistoryRange,
} from "@/lib/dashboard-data";
import type { ChainSlug } from "@/lib/public-api/contracts";

const chainSlugs: readonly ChainSlug[] = ["btc", "eth", "sol", "bnb"];

function ChartLoading() {
  const t = useTranslations("states");
  return (
    <div role="status" aria-label={t("loading")} className="rounded-xl border border-border p-4">
      <span className="sr-only">{t("loading")}</span>
      <Skeleton className="h-8 w-1/3" />
      <Skeleton className="mt-4 h-64 w-full" />
    </div>
  );
}

const DynamicScoreHistoryChart = dynamic(
  () =>
    import("./score-history-chart").then((module) => module.ScoreHistoryChart),
  { ssr: false, loading: ChartLoading },
);

export function ScoreHistoryChartLoader() {
  const t = useTranslations("dashboard");
  const [range, setRange] = useState<ScoreHistoryRange>("1y");
  const dateRange = getScoreHistoryDateRange(range);
  const results = useQueries({
    queries: chainSlugs.map((slug) => ({
      queryKey: publicQueryKeys.scoreHistory(slug, dateRange),
      queryFn: () => getScoreHistory(slug, dateRange),
    })),
  });

  if (results.some((result) => result.isPending)) return <ChartLoading />;
  const failed = results.find((result) => result.isError);
  if (failed) {
    return (
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">{t("chartTitle")}</h2>
        <PublicApiErrorState
          error={failed.error}
          onRetry={() => {
            results.forEach((result) => void result.refetch());
          }}
        />
      </section>
    );
  }

  const series = results.flatMap((result, index) =>
    result.data
      ? [{ slug: chainSlugs[index], items: result.data.items }]
      : [],
  );
  const data = buildScoreHistoryChartData(
    series,
    dateRange,
  );

  return (
    <DynamicScoreHistoryChart
      data={data}
      range={range}
      onRangeChange={setRange}
    />
  );
}