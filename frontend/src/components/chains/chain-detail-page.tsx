"use client";

import { AlertTriangle, CircleAlert, Info } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { Link } from "@/i18n/navigation";
import { PartialBadge } from "@/components/dashboard/chain-card";
import { ChainDetailChartsLoader } from "@/components/chains/chain-detail-charts-loader";
import { ScenarioHorizonCard } from "@/components/chains/scenario-horizon-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TooltipProvider } from "@/components/ui/tooltip";
import { PublicApiErrorState } from "@/components/states/public-api-error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { PriceValue, ReturnValue } from "@/components/app/return-value";
import { ScoreDisplay } from "@/components/app/score-display";
import { chainNameKeys } from "@/components/app/chain-labels";
import {
  getChainDetail,
  getMethodology,
  getRegimes,
  getScenarios,
  getScoreHistory,
  getSeries,
  ApiError,
} from "@/lib/public-api/client";
import {
  type ChainDetailResponse,
  type ChainSlug,
  type MethodologyResponse,
  type RegimesResponse,
} from "@/lib/public-api/contracts";
import { publicQueryKeys } from "@/lib/public-api/query-keys";
import {
  buildChainScoreHistoryData,
  buildPriceSeriesData,
  buildRegimeTimeline,
} from "@/lib/chain-detail-data";
import {
  formatCoverage,
  formatScore,
  getScoreHistoryDateRange,
  type ScoreHistoryRange,
} from "@/lib/dashboard-data";

function SectionLoading() {
  const t = useTranslations("states");
  return (
    <div
      role="status"
      aria-label={t("loading")}
      className="space-y-3 rounded-xl border border-border p-4"
    >
      <span className="sr-only">{t("loading")}</span>
      <Skeleton className="h-5 w-1/3" />
      <Skeleton className="h-20 w-full" />
    </div>
  );
}

function SectionEmpty({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-border bg-muted/20 p-5 text-sm text-muted">
      {message}
    </div>
  );
}

function SectionState({
  isPending,
  isError,
  error,
  isEmpty,
  emptyMessage,
  onRetry,
  children,
}: {
  isPending: boolean;
  isError: boolean;
  error: unknown;
  isEmpty: boolean;
  emptyMessage: string;
  onRetry: () => void;
  children: React.ReactNode;
}) {
  if (isPending) return <SectionLoading />;
  if (isError) return <PublicApiErrorState error={error} onRetry={onRetry} />;
  if (isEmpty) return <SectionEmpty message={emptyMessage} />;
  return children;
}

function sectionTitleId(
  section: "snapshot" | "history" | "timeline" | "price" | "scenarios",
): string {
  return `chain-detail-${section}`;
}

const knownFlags = [
  "deep_drawdown",
  "high_volatility",
  "liquidity_drying",
  "usage_decline",
  "tvl_outflow",
  "stablecoin_contraction",
] as const;

const pillarNameKeys: Record<string, "pillarNames.adoption" | "pillarNames.capital" | "pillarNames.market_condition" | "pillarNames.security_economics"> = {
  adoption: "pillarNames.adoption",
  capital: "pillarNames.capital",
  market_condition: "pillarNames.market_condition",
  security_economics: "pillarNames.security_economics",
} as const;

const chainSymbols: Record<ChainSlug, string> = {
  btc: "BTC",
  eth: "ETH",
  sol: "SOL",
  bnb: "BNB",
};

function regimeTranslationKey(regime: string): string {
  return regime === "uptrend" || regime === "downtrend" || regime === "range"
    ? `regimes.${regime}`
    : "unknownRegime";
}

function volatilityTranslationKey(volatility: string): string {
  return volatility === "low" ||
    volatility === "normal" ||
    volatility === "high"
    ? `volatility.${volatility}`
    : "unknownVolatility";
}

function flagTranslationKey(flag: string): string {
  return (knownFlags as readonly string[]).includes(flag)
    ? `flags.${flag}`
    : "unknownFlag";
}

function severityTranslationKey(severity: string): string {
  return severity === "low" || severity === "medium" || severity === "high"
    ? `severity.${severity}`
    : "severity.unknown";
}

function SeverityIcon({ severity }: { severity: string }) {
  const Icon =
    severity === "high"
      ? AlertTriangle
      : severity === "low"
        ? Info
        : CircleAlert;
  return <Icon className="size-4 text-muted" aria-hidden="true" />;
}

function Snapshot({
  detail,
  isLoading,
  isError,
}: {
  detail: ChainDetailResponse;
  isLoading: boolean;
  isError: boolean;
}) {
  const t = useTranslations("chainDetail");
  const dashboardT = useTranslations("dashboard");
  const scoreSummary = detail.score;

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>{dashboardT("tooltipScore")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <TooltipProvider>
              <ScoreDisplay score={scoreSummary} />
              <PartialBadge
                chain={detail}
                lastFullCoverage={detail.last_full_coverage ?? undefined}
                isLoading={isLoading}
                isError={isError}
              />
            </TooltipProvider>
          </div>
          {scoreSummary && (
            <p className="text-sm text-muted">
              {dashboardT.rich("coverage", {
                ltr: (chunks) => (
                  <bdi dir="ltr" className="tabular-nums">
                    {chunks}
                  </bdi>
                ),
                coverage: formatCoverage(scoreSummary.coverage),
                coverageMax: formatCoverage(scoreSummary.coverage_max),
              })}
            </p>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <h3 className="text-sm font-medium">{dashboardT("price")}</h3>
              <PriceValue value={detail.price.close_usd} />
              <p className="text-sm text-muted">{dashboardT("return30d")}</p>
              <ReturnValue value={detail.price.ret_30d} />
            </div>
            <div className="space-y-2">
              <h3 className="text-sm font-medium">{t("regimeLabel")}</h3>
              {detail.regime ? (
                <>
                  <span className="inline-flex rounded-full border border-border bg-muted/40 px-2 py-1 text-sm">
                    {dashboardT(regimeTranslationKey(detail.regime.label))}
                    <span className="ms-2 text-muted">
                      <bdi dir="ltr" className="tabular-nums">
                        {new Intl.NumberFormat("en-US").format(
                          detail.regime.days_in_regime,
                        )}
                      </bdi>{" "}
                      {dashboardT("daysCount")}
                    </span>
                  </span>
                  {detail.regime.vol_state && (
                    <p className="text-sm text-muted">
                      {dashboardT(
                        volatilityTranslationKey(detail.regime.vol_state),
                      )}
                    </p>
                  )}
                </>
              ) : (
                <p className="text-sm text-muted">{dashboardT("notAvailable")}</p>
              )}
            </div>
          </div>
          <div className="space-y-2">
            <h3 className="text-sm font-medium">{dashboardT("activeFlags")}</h3>
            {detail.flags.length === 0 ? (
              <p className="text-sm text-muted">
                {dashboardT("noActiveFlags")}
              </p>
            ) : (
              <ul className="flex flex-wrap gap-2">
                {detail.flags.map((flag) => (
                  <li
                    key={flag.flag}
                    className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/40 px-3 py-1 text-sm"
                  >
                    <SeverityIcon severity={flag.severity} />
                    <span>{dashboardT(flagTranslationKey(flag.flag))}</span>
                    <span className="text-muted">
                      {dashboardT(severityTranslationKey(flag.severity))}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {detail.freshness.stale && (
            <p className="text-sm text-muted">{dashboardT("staleWarning")}</p>
          )}
          {detail.freshness.lag_days !== null && (
            <p className="text-xs text-muted">
              {dashboardT("priceDataPrefix")}{" "}
              <bdi dir="ltr" className="tabular-nums">
                {detail.freshness.price_last_date ?? dashboardT("notAvailable")}
              </bdi>
              {detail.freshness.lag_days > 0 && (
                <>
                  {" · "}
                  {new Intl.NumberFormat("en-US").format(
                    detail.freshness.lag_days,
                  )}{" "}
                  {dashboardT("daysCount")}
                </>
              )}
            </p>
          )}
          <p className="text-xs text-muted">
            {t("methodologyVersion", { version: detail.methodology_version })}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function ScorePillars({
  detail,
  methodology,
  isPending,
  isError,
  error,
  onRetry,
}: {
  detail: ChainDetailResponse;
  methodology: MethodologyResponse | undefined;
  isPending: boolean;
  isError: boolean;
  error: unknown;
  onRetry: () => void;
}) {
  const t = useTranslations("chainDetail");
  if (!detail.score) {
    return <SectionEmpty message={t("emptySnapshot")} />;
  }

  return (
    <section className="space-y-3" aria-labelledby="chain-detail-pillars">
      <h3 id="chain-detail-pillars" className="font-semibold">
        {t("pillarsTitle")}
      </h3>
      <SectionState
        isPending={isPending}
        isError={isError}
        error={error}
        isEmpty={!methodology || methodology.pillars.length === 0}
        emptyMessage={t("pillarUnavailable")}
        onRetry={onRetry}
      >
        <ul className="grid gap-3 sm:grid-cols-2">
          {methodology?.pillars.map((pillar) => {
            const pillarScore = detail.score?.pillars[pillar.name];
            return (
              <li
                key={pillar.name}
                className="rounded-lg border border-border bg-card p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h4 className="font-medium">
                    {pillarNameKeys[pillar.name]
                      ? t(pillarNameKeys[pillar.name])
                      : t("unknownPillar")}
                  </h4>
                  <span className="text-xs text-muted">
                    {t("pillarNominalWeight")}{" "}
                    <bdi dir="ltr" className="tabular-nums">
                      {new Intl.NumberFormat("en-US").format(pillar.weight)}%
                    </bdi>
                  </span>
                </div>
                {pillarScore?.available &&
                pillarScore.score !== null ? (
                  <p dir="ltr" className="mt-2 tabular-nums">
                    {formatScore(pillarScore.score)}
                  </p>
                ) : (
                  <p className="mt-2 text-sm text-muted">
                    {t("pillarUnavailable")}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      </SectionState>
    </section>
  );
}

function RegimeTimeline({
  regimes,
}: {
  regimes: RegimesResponse;
}) {
  const t = useTranslations("chainDetail");
  const dashboardT = useTranslations("dashboard");
  const timeline = buildRegimeTimeline(regimes.segments);

  return (
    <ol
      dir="ltr"
      data-testid="regime-timeline-wrapper"
      className="space-y-2"
    >
      {timeline.map((segment) => (
        <li
          key={`${segment.start_date}-${segment.end_date}-${segment.regime}`}
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted/20 px-4 py-3"
        >
          <span className="rounded-full border border-border bg-card px-2 py-1 text-sm">
            {dashboardT(regimeTranslationKey(segment.regime))}
          </span>
          <bdi className="tabular-nums text-sm text-muted">
            {segment.start_date} — {segment.end_date}
          </bdi>
          <span className="text-sm text-muted">
            {t("timelineDays", {
              days: new Intl.NumberFormat("en-US").format(segment.days),
            })}
          </span>
        </li>
      ))}
    </ol>
  );
}

function sourceName(
  methodology: MethodologyResponse | undefined,
  sourceId: string,
): string | null {
  const normalize = (value: string) => value.toLowerCase().replace(/[^a-z0-9]/g, "");
  const normalizedId = normalize(sourceId);
  return (
    methodology?.sources.find(
      (source) => normalize(source.name) === normalizedId,
    )?.name ?? null
  );
}

function ChainNotFoundState() {
  const t = useTranslations("chainDetail");
  return (
    <section
      role="status"
      className="mx-auto max-w-xl rounded-xl border border-border bg-card p-6 text-center"
    >
      <h1 className="text-xl font-semibold">{t("notFoundTitle")}</h1>
      <p className="mt-2 text-sm text-muted">{t("notFoundDescription")}</p>
      <Button asChild className="mt-5" variant="outline">
        <Link href="/app/chains">{t("backToScreener")}</Link>
      </Button>
    </section>
  );
}

export function ChainNotFoundPage() {
  return <ChainNotFoundState />;
}

export function ChainDetailPage({ slug }: { slug: ChainSlug }) {
  const locale = useLocale();
  const t = useTranslations("chainDetail");
  const dashboardT = useTranslations("dashboard");
  const [range, setRange] = useState<ScoreHistoryRange>("1y");
  const dateRange = getScoreHistoryDateRange(range);
  const detailQuery = useQuery({
    queryKey: publicQueryKeys.chain(slug),
    queryFn: () => getChainDetail(slug),
  });
  const scoreHistoryQuery = useQuery({
    queryKey: publicQueryKeys.scoreHistory(slug, dateRange),
    queryFn: () => getScoreHistory(slug, dateRange),
  });
  const regimesQuery = useQuery({
    queryKey: publicQueryKeys.regimes(slug),
    queryFn: () => getRegimes(slug),
  });
  const priceSeriesQuery = useQuery({
    queryKey: publicQueryKeys.series(slug, "price_close_usd", "binance"),
    queryFn: () => getSeries(slug, "price_close_usd", "binance"),
  });
  const scenariosQuery = useQuery({
    queryKey: publicQueryKeys.scenarios(slug),
    queryFn: () => getScenarios(slug),
  });
  const methodologyQuery = useQuery({
    queryKey: publicQueryKeys.methodology,
    queryFn: getMethodology,
  });

  const detailNotFound =
    detailQuery.error instanceof ApiError &&
    detailQuery.error.code === "chain_not_found";
  if (detailNotFound) return <ChainNotFoundState />;

  const chainName = dashboardT(chainNameKeys[slug]);
  const detail = detailQuery.data;
  const priceDate =
    detail?.price.as_of_date ?? detail?.freshness.price_last_date ?? null;
  const scoreChartData = scoreHistoryQuery.data
    ? buildChainScoreHistoryData(scoreHistoryQuery.data.items, dateRange)
    : [];
  const priceChartData = priceSeriesQuery.data
    ? buildPriceSeriesData(priceSeriesQuery.data.points)
    : [];
  const source = priceSeriesQuery.data
    ? sourceName(methodologyQuery.data, priceSeriesQuery.data.meta.source)
    : null;

  return (
    <main
      dir={locale === "fa" ? "rtl" : "ltr"}
      className="mx-auto max-w-6xl space-y-8"
    >
      <header className="space-y-4">
        <Link
          href="/app/chains"
          className="inline-flex rounded-sm text-sm text-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {t("backToScreener")}
        </Link>
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">
            {chainName}{" "}
            <bdi dir="ltr" className="text-muted">
              ({detail?.symbol ?? chainSymbols[slug]})
            </bdi>
          </h1>
          <p className="text-sm text-muted">
            {dashboardT("dataAsOfPrefix")}{" "}
            <bdi dir="ltr" className="tabular-nums">
              {priceDate ?? dashboardT("notAvailable")}
            </bdi>{" "}
            ({dashboardT("utc")})
          </p>
          <p className="text-sm text-muted">{dashboardT("disclaimer")}</p>
        </div>
      </header>

      <section
        className="space-y-4"
        aria-labelledby={sectionTitleId("snapshot")}
      >
        <h2
          id={sectionTitleId("snapshot")}
          className="text-xl font-semibold"
        >
          {t("snapshotTitle")}
        </h2>
        <SectionState
          isPending={detailQuery.isPending}
          isError={detailQuery.isError}
          error={detailQuery.error}
          isEmpty={!detail}
          emptyMessage={t("emptySnapshot")}
          onRetry={() => void detailQuery.refetch()}
        >
          {detail && (
            <Snapshot
              detail={detail}
              isLoading={detailQuery.isPending}
              isError={detailQuery.isError}
            />
          )}
        </SectionState>
        {detail?.score && (
          <ScorePillars
            detail={detail}
            methodology={methodologyQuery.data}
            isPending={methodologyQuery.isPending}
            isError={methodologyQuery.isError}
            error={methodologyQuery.error}
            onRetry={() => void methodologyQuery.refetch()}
          />
        )}
      </section>

      <section
        className="space-y-4"
        aria-labelledby={sectionTitleId("history")}
      >
        <h2
          id={sectionTitleId("history")}
          className="text-xl font-semibold"
        >
          {t("historyTitle")}
        </h2>
        <SectionState
          isPending={scoreHistoryQuery.isPending}
          isError={scoreHistoryQuery.isError}
          error={scoreHistoryQuery.error}
          isEmpty={scoreHistoryQuery.data?.items.length === 0}
          emptyMessage={t("emptyHistory")}
          onRetry={() => void scoreHistoryQuery.refetch()}
        >
          <div dir="ltr" data-testid="score-chart-wrapper">
            <ChainDetailChartsLoader
              scoreData={scoreChartData}
              priceData={priceChartData}
              range={range}
              onRangeChange={setRange}
              showScore
              showPrice={false}
            />
          </div>
        </SectionState>
      </section>

      <section
        className="space-y-4"
        aria-labelledby={sectionTitleId("timeline")}
      >
        <h2
          id={sectionTitleId("timeline")}
          className="text-xl font-semibold"
        >
          {t("timelineTitle")}
        </h2>
        <SectionState
          isPending={regimesQuery.isPending}
          isError={regimesQuery.isError}
          error={regimesQuery.error}
          isEmpty={regimesQuery.data?.segments.length === 0}
          emptyMessage={t("emptyTimeline")}
          onRetry={() => void regimesQuery.refetch()}
        >
          {regimesQuery.data && (
            <RegimeTimeline regimes={regimesQuery.data} />
          )}
        </SectionState>
      </section>

      <section
        className="space-y-4"
        aria-labelledby={sectionTitleId("price")}
      >
        <div className="space-y-1">
          <h2
            id={sectionTitleId("price")}
            className="text-xl font-semibold"
          >
            {t("priceHistoryTitle")}
          </h2>
          <p className="text-sm text-muted">
            {t("priceSource", {
              source: source ?? t("sourceUnavailable"),
            })}
          </p>
          {methodologyQuery.isError && (
            <PublicApiErrorState
              error={methodologyQuery.error}
              onRetry={() => void methodologyQuery.refetch()}
            />
          )}
        </div>
        <SectionState
          isPending={priceSeriesQuery.isPending}
          isError={priceSeriesQuery.isError}
          error={priceSeriesQuery.error}
          isEmpty={priceSeriesQuery.data?.points.length === 0}
          emptyMessage={t("emptyPriceHistory")}
          onRetry={() => void priceSeriesQuery.refetch()}
        >
          <div dir="ltr" data-testid="price-chart-wrapper">
            <ChainDetailChartsLoader
              scoreData={scoreChartData}
              priceData={priceChartData}
              range={range}
              onRangeChange={setRange}
              showScore={false}
              showPrice
            />
          </div>
        </SectionState>
      </section>

      <section
        className="space-y-4"
        aria-labelledby={sectionTitleId("scenarios")}
      >
        <div className="space-y-2">
          <h2
            id={sectionTitleId("scenarios")}
            className="text-xl font-semibold"
          >
            {t("scenariosTitle")}
          </h2>
          <p className="font-medium">{t("historicalQuantilesNote")}</p>
          <p className="text-sm text-muted">{t("quantileExplanation")}</p>
        </div>
        <SectionState
          isPending={scenariosQuery.isPending}
          isError={scenariosQuery.isError}
          error={scenariosQuery.error}
          isEmpty={scenariosQuery.data?.horizons.length === 0}
          emptyMessage={t("emptyScenarios")}
          onRetry={() => void scenariosQuery.refetch()}
        >
          <div className="grid gap-4 lg:grid-cols-3">
            {scenariosQuery.data?.horizons.map((horizon) => (
              <ScenarioHorizonCard
                key={horizon.days}
                horizon={horizon}
              />
            ))}
          </div>
        </SectionState>
      </section>
    </main>
  );
}
