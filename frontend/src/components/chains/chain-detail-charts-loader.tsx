"use client";

import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import type { ChainChartPoint } from "@/lib/chain-detail-data";
import type { ScoreHistoryRange } from "@/lib/dashboard-data";
import { Skeleton } from "@/components/ui/skeleton";

function ChartsLoading() {
  const t = useTranslations("states");
  return (
    <div role="status" aria-label={t("loading")} className="space-y-3">
      <span className="sr-only">{t("loading")}</span>
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

const DynamicChainDetailCharts = dynamic(
  () =>
    import("./chain-detail-charts").then(
      (module) => module.ChainDetailCharts,
    ),
  { ssr: false, loading: ChartsLoading },
);

export function ChainDetailChartsLoader({
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
  return (
    <DynamicChainDetailCharts
      scoreData={scoreData}
      priceData={priceData}
      range={range}
      onRangeChange={onRangeChange}
      showScore={showScore}
      showPrice={showPrice}
    />
  );
}
