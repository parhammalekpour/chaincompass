"use client";

import { Activity, CircleAlert } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { getChains } from "@/lib/public-api/client";
import { publicQueryKeys } from "@/lib/public-api/query-keys";
import { usePartialCoverageDetails } from "@/hooks/use-partial-coverage-details";
import { freshestPriceDate } from "@/lib/dashboard-data";
import { EmptyState } from "@/components/states/empty-state";
import { PublicApiErrorState } from "@/components/states/public-api-error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { ChainCard } from "./chain-card";
import { DashboardFrame } from "./dashboard-frame";
import { ScoreHistoryChartLoader } from "./score-history-chart-loader";
import type { AppLocale } from "@/lib/format";
import type { ChainSlug } from "@/lib/public-api/contracts";

function DashboardSkeleton() {
  const t = useTranslations("states");
  return (
    <div role="status" aria-label={t("loading")} className="space-y-6">
      <span className="sr-only">{t("loading")}</span>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {["btc", "eth", "sol", "bnb"].map((slug) => (
          <div key={slug} className="space-y-3 rounded-xl border border-border p-4">
            <Skeleton className="h-5 w-2/5" />
            <Skeleton className="h-8 w-3/5" />
            <Skeleton className="h-4 w-full" />
          </div>
        ))}
      </div>
      <Skeleton className="h-80 w-full rounded-xl" />
    </div>
  );
}

export function DashboardPage() {
  const locale = (useLocale() === "fa" ? "fa" : "en") as AppLocale;
  const t = useTranslations("dashboard");
  const chainsQuery = useQuery({
    queryKey: publicQueryKeys.chains,
    queryFn: getChains,
  });
  const chains = chainsQuery.data?.chains ?? [];
  const partialSlugs: ChainSlug[] = chains
    .filter((chain) => chain.score?.is_partial)
    .map((chain) => chain.slug);
  const detailsQueries = usePartialCoverageDetails(partialSlugs);

  if (chainsQuery.isPending) return <DashboardSkeleton />;
  if (chainsQuery.isError && !chainsQuery.data) {
    return (
      <PublicApiErrorState
        error={chainsQuery.error}
        onRetry={() => void chainsQuery.refetch()}
      />
    );
  }
  if (chains.length === 0) {
    return (
      <DashboardFrame locale={locale}>
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
          <p className="text-sm text-muted">{t("description")}</p>
        </header>
        <EmptyState
          icon={Activity}
          title={t("emptyTitle")}
          description={t("emptyDescription")}
        />
      </DashboardFrame>
    );
  }

  const detailBySlug = new Map(
    partialSlugs.map((slug, index) => [slug, detailsQueries[index]]),
  );
  const dataAsOf = freshestPriceDate(
    chains.map((chain) => chain.price.as_of_date ?? chain.freshness.price_last_date),
  );

  return (
    <DashboardFrame locale={locale}>
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-sm text-muted">{t("description")}</p>
        <p className="text-sm text-muted">
          <span>{t("dataAsOfPrefix")} </span>
          {dataAsOf ? (
            <time dir="ltr" dateTime={dataAsOf}>{dataAsOf}</time>
          ) : (
            t("notAvailable")
          )}{" "}
          (<span dir="ltr">{t("utc")}</span>)
        </p>
        <p className="max-w-3xl text-sm text-muted">{t("disclaimer")}</p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {chains.map((chain) => {
          const detailQuery = detailBySlug.get(chain.slug);
          return (
            <ChainCard
              key={chain.slug}
              chain={chain}
              lastFullCoverage={
                detailQuery?.data?.last_full_coverage ?? undefined
              }
              isLastFullCoverageLoading={detailQuery?.isPending ?? false}
              isLastFullCoverageError={detailQuery?.isError ?? false}
            />
          );
        })}
      </div>
      {chainsQuery.isError && (
        <div className="flex items-start gap-2 rounded-lg border border-border p-3 text-sm text-muted">
          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>{t("refreshError")}</span>
        </div>
      )}
      <ScoreHistoryChartLoader />
    </DashboardFrame>
  );
}