"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useSyncExternalStore,
} from "react";
import { Activity, ArrowDown, ArrowUp, ListFilter, TriangleAlert } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { useQuery } from "@tanstack/react-query";
import { getChains } from "@/lib/public-api/client";
import { publicQueryKeys } from "@/lib/public-api/query-keys";
import { freshestPriceDate } from "@/lib/dashboard-data";
import type { AppLocale } from "@/lib/format";
import type { ChainSummary } from "@/lib/public-api/contracts";
import {
  filterAndSortChains,
  parseScreenerParams,
  serializeScreenerParams,
  type ScreenerConfidence,
  type ScreenerDirection,
  type ScreenerRegime,
  type ScreenerSortKey,
  type ScreenerState,
} from "@/lib/chains-screener";
import { chainNameKeys } from "@/components/app/chain-labels";
import { PriceValue, ReturnValue } from "@/components/app/return-value";
import { ScoreDisplay } from "@/components/app/score-display";
import { DashboardFrame } from "@/components/dashboard/dashboard-frame";
import { EmptyState } from "@/components/states/empty-state";
import { PublicApiErrorState } from "@/components/states/public-api-error-state";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";

const sortKeys: readonly ScreenerSortKey[] = [
  "chain",
  "score",
  "regime",
  "volatility",
  "price",
  "return",
  "flags",
  "freshness",
];

const regimes: readonly ScreenerRegime[] = [
  "all",
  "uptrend",
  "downtrend",
  "range",
];

const confidences: readonly ScreenerConfidence[] = [
  "all",
  "High",
  "Medium",
  "Low",
];

const flagKeys: Record<string, string> = {
  deep_drawdown: "deep_drawdown",
  high_volatility: "high_volatility",
  liquidity_drying: "liquidity_drying",
  usage_decline: "usage_decline",
  tvl_outflow: "tvl_outflow",
  stablecoin_contraction: "stablecoin_contraction",
};
const screenerUrlEvent = "chaincompass:screener-url-change";

function subscribeToSearch(onChange: () => void) {
  window.addEventListener("popstate", onChange);
  window.addEventListener(screenerUrlEvent, onChange);
  return () => {
    window.removeEventListener("popstate", onChange);
    window.removeEventListener(screenerUrlEvent, onChange);
  };
}

function getBrowserSearch() {
  return window.location.search;
}

function getServerSearch() {
  return "";
}

function ScreenerSkeleton() {
  const t = useTranslations("states");
  return (
    <div role="status" aria-label={t("loading")} className="space-y-4">
      <span className="sr-only">{t("loading")}</span>
      {["a", "b", "c", "d"].map((item) => (
        <Skeleton key={item} className="h-24 w-full rounded-xl" />
      ))}
    </div>
  );
}

function localizedFlag(flag: string, t: ReturnType<typeof useTranslations>) {
  const key = flagKeys[flag];
  return key ? t(`flags.${key}`) : t("unknownFlag");
}

function chainName(
  chain: ChainSummary,
  t: ReturnType<typeof useTranslations>,
) {
  return t(chainNameKeys[chain.slug]);
}

function RiskFlagCount({
  chain,
}: {
  chain: ChainSummary;
}) {
  const t = useTranslations("dashboard");
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="outline"
            size="xs"
            dir="ltr"
            aria-label={t("flagCount", { count: chain.flags.length })}
          >
            <TriangleAlert className="size-3.5 text-muted" aria-hidden="true" />
            {chain.flags.length}
          </Button>
        </TooltipTrigger>
        <TooltipContent className="max-w-sm whitespace-normal">
          {chain.flags.length === 0 ? (
            <span>{t("noActiveFlags")}</span>
          ) : (
            <ul className="space-y-1">
              {chain.flags.map((flag) => (
                <li key={`${flag.flag}-${flag.severity}`}>
                  {localizedFlag(flag.flag, t)}
                </li>
              ))}
            </ul>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function RegimeValue({ chain }: { chain: ChainSummary }) {
  const t = useTranslations("dashboard");
  if (!chain.regime) return <span className="text-muted">{t("notAvailable")}</span>;
  const label =
    chain.regime.label === "uptrend" ||
    chain.regime.label === "downtrend" ||
    chain.regime.label === "range"
      ? t(`regimes.${chain.regime.label}`)
      : t("unknownRegime");
  const volatility =
    chain.regime.vol_state === "low" ||
    chain.regime.vol_state === "normal" ||
    chain.regime.vol_state === "high"
      ? t(`volatility.${chain.regime.vol_state}`)
      : t("unknownVolatility");
  return (
    <div className="flex flex-wrap gap-1">
      <span className="rounded-full border border-border bg-muted/40 px-2 py-0.5 text-xs">
        {label}
      </span>
      <span className="rounded-full border border-border bg-muted/40 px-2 py-0.5 text-xs">
        {volatility}
      </span>
    </div>
  );
}

function ScreenerCard({ chain }: { chain: ChainSummary }) {
  const t = useTranslations("dashboard");
  const name = chainName(chain, t);
  return (
    <Card size="sm">
      <CardHeader className="gap-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className="text-base">
              <Link
                href={`/app/chains/${chain.slug}`}
                className="rounded-sm hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {name}
              </Link>
            </CardTitle>
            <span dir="ltr" className="text-xs text-muted">{chain.symbol}</span>
          </div>
          <RiskFlagCount chain={chain} />
        </div>
        <div className="space-y-2">
          <ScoreDisplay score={chain.score} />
          {chain.score?.is_partial && (
            <span className="inline-flex rounded-full border border-border px-2 py-0.5 text-xs">
              {t("partial")}
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <RegimeValue chain={chain} />
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-xs text-muted">{t("price")}</dt>
            <dd><PriceValue value={chain.price.close_usd} /></dd>
          </div>
          <div>
            <dt className="text-xs text-muted">{t("return30d")}</dt>
            <dd><ReturnValue value={chain.price.ret_30d} /></dd>
          </div>
        </dl>
        <p className="text-xs text-muted">
          <span>{t("priceDataPrefix")} </span>
          {chain.freshness.price_last_date ? (
            <time dir="ltr" dateTime={chain.freshness.price_last_date}>
              {chain.freshness.price_last_date}
            </time>
          ) : (
            t("notAvailable")
          )}
        </p>
      </CardContent>
    </Card>
  );
}

export function ChainsScreenerPage() {
  const locale = (useLocale() === "fa" ? "fa" : "en") as AppLocale;
  const t = useTranslations("screener");
  const dashboardT = useTranslations("dashboard");
  const chainsQuery = useQuery({
    queryKey: publicQueryKeys.chains,
    queryFn: getChains,
  });
  const chains = useMemo(
    () => chainsQuery.data?.chains ?? [],
    [chainsQuery.data],
  );
  const search = useSyncExternalStore(
    subscribeToSearch,
    getBrowserSearch,
    getServerSearch,
  );
  const state = useMemo(() => parseScreenerParams(search), [search]);

  const writeUrlState = useCallback((next: ScreenerState) => {
    const query = serializeScreenerParams(next);
    const suffix = window.location.hash;
    window.history.replaceState(
      window.history.state,
      "",
      `${window.location.pathname}?${query}${suffix}`,
    );
    window.dispatchEvent(new Event(screenerUrlEvent));
  }, []);

  useEffect(() => {
    const fromUrl = parseScreenerParams(window.location.search);
    const canonicalSearch = `?${serializeScreenerParams(fromUrl)}`;
    if (window.location.search !== canonicalSearch) {
      writeUrlState(fromUrl);
    }
  }, [writeUrlState]);

  const updateState = (next: ScreenerState) => {
    writeUrlState(next);
  };

  const visibleChains = useMemo(
    () => filterAndSortChains(chains, state),
    [chains, state],
  );
  const dataAsOf = freshestPriceDate(
    chains.map((chain) => chain.price.as_of_date ?? chain.freshness.price_last_date),
  );

  if (chainsQuery.isPending) return <ScreenerSkeleton />;
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

  const sortBy = (sort: ScreenerSortKey) => {
    const direction: ScreenerDirection =
      state.sort === sort && state.direction === "asc" ? "desc" : "asc";
    updateState({ ...state, sort, direction });
  };

  const ariaSort = (sort: ScreenerSortKey) =>
    state.sort === sort
      ? state.direction === "asc"
        ? "ascending"
        : "descending"
      : "none";

  const renderSortHeader = (sort: ScreenerSortKey) => (
    <TableHead key={sort} aria-sort={ariaSort(sort)}>
      <button
        type="button"
        className="inline-flex items-center gap-1 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        onClick={() => sortBy(sort)}
      >
        {t(`columns.${sort}`)}
        {state.sort === sort &&
          (state.direction === "asc" ? (
            <ArrowUp className="size-3.5" aria-hidden="true" />
          ) : (
            <ArrowDown className="size-3.5" aria-hidden="true" />
          ))}
      </button>
    </TableHead>
  );

  const clearFilters = () =>
    updateState({
      ...state,
      regime: "all",
      confidence: "all",
      hasRiskFlags: false,
    });

  return (
    <DashboardFrame locale={locale}>
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-sm text-muted">{t("description")}</p>
        <p className="text-sm text-muted">
          <span>{dashboardT("dataAsOfPrefix")} </span>
          {dataAsOf ? (
            <time dir="ltr" dateTime={dataAsOf}>{dataAsOf}</time>
          ) : (
            dashboardT("notAvailable")
          )}{" "}
          (<span dir="ltr">{dashboardT("utc")}</span>)
        </p>
        <p className="max-w-3xl text-sm text-muted">{dashboardT("disclaimer")}</p>
      </header>

      <section
        aria-label={t("filters")}
        className="flex flex-wrap items-end gap-3 rounded-xl border border-border bg-card p-4"
      >
        <div className="grid gap-1.5">
          <label htmlFor="regime-filter" className="text-xs font-medium text-muted">
            {t("regimeFilter")}
          </label>
          <Select
            id="regime-filter"
            value={state.regime}
            onChange={(event) =>
              updateState({
                ...state,
                regime: event.target.value as ScreenerRegime,
              })
            }
          >
            {regimes.map((regime) => (
              <option key={regime} value={regime}>
                {t(`regimes.${regime}`)}
              </option>
            ))}
          </Select>
        </div>
        <div className="grid gap-1.5">
          <label
            htmlFor="confidence-filter"
            className="text-xs font-medium text-muted"
          >
            {t("confidenceFilter")}
          </label>
          <Select
            id="confidence-filter"
            value={state.confidence}
            onChange={(event) =>
              updateState({
                ...state,
                confidence: event.target.value as ScreenerConfidence,
              })
            }
          >
            {confidences.map((confidence) => (
              <option key={confidence} value={confidence}>
                {t(`confidence.${confidence.toLowerCase()}`)}
              </option>
            ))}
          </Select>
        </div>
        <label className="flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm">
          <input
            type="checkbox"
            checked={state.hasRiskFlags}
            onChange={(event) =>
              updateState({ ...state, hasRiskFlags: event.target.checked })
            }
            className="size-4 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          {t("hasRiskFlags")}
        </label>
        <div className="grid gap-1.5">
          <label htmlFor="sort-filter" className="text-xs font-medium text-muted">
            {t("sortBy")}
          </label>
          <Select
            id="sort-filter"
            value={state.sort}
            onChange={(event) =>
              updateState({
                ...state,
                sort: event.target.value as ScreenerSortKey,
              })
            }
          >
            {sortKeys.map((sort) => (
              <option key={sort} value={sort}>
                {t(`columns.${sort}`)}
              </option>
            ))}
          </Select>
        </div>
        <Button variant="outline" onClick={clearFilters}>
          <ListFilter aria-hidden="true" />
          {t("clearFilters")}
        </Button>
      </section>

      {visibleChains.length === 0 ? (
        <EmptyState
          icon={ListFilter}
          title={t("noResultsTitle")}
          description={t("noResultsDescription")}
          action={{ label: t("clearFilters"), onClick: clearFilters }}
        />
      ) : (
        <>
          <div className="hidden md:block">
            <TooltipProvider>
              <Table>
                <TableHeader>
                  <TableRow>
                    {sortKeys.map(renderSortHeader)}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleChains.map((chain) => (
                    <TableRow key={chain.slug}>
                      <TableCell>
                        <Link
                          href={`/app/chains/${chain.slug}`}
                          className="font-medium hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          {chainName(chain, dashboardT)}
                          <span dir="ltr" className="ms-2 text-xs text-muted">
                            {chain.symbol}
                          </span>
                        </Link>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap items-center gap-2">
                          <ScoreDisplay score={chain.score} />
                          {chain.score?.is_partial && (
                            <span className="rounded-full border border-border px-2 py-0.5 text-xs">
                              {dashboardT("partial")}
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell><RegimeValue chain={chain} /></TableCell>
                      <TableCell>
                        {chain.regime?.vol_state === "low" ||
                        chain.regime?.vol_state === "normal" ||
                        chain.regime?.vol_state === "high"
                          ? dashboardT(`volatility.${chain.regime.vol_state}`)
                          : dashboardT("unknownVolatility")}
                      </TableCell>
                      <TableCell><PriceValue value={chain.price.close_usd} /></TableCell>
                      <TableCell><ReturnValue value={chain.price.ret_30d} /></TableCell>
                      <TableCell><RiskFlagCount chain={chain} /></TableCell>
                      <TableCell>
                        {chain.freshness.price_last_date ??
                        chain.price.as_of_date ? (
                          <time
                            dir="ltr"
                            dateTime={
                              chain.freshness.price_last_date ??
                              chain.price.as_of_date ??
                              undefined
                            }
                          >
                            {chain.freshness.price_last_date ??
                              chain.price.as_of_date}
                          </time>
                        ) : (
                          dashboardT("notAvailable")
                        )}
                        {chain.freshness.stale && (
                          <span className="ms-1 inline-flex items-center gap-1 text-muted">
                            <TriangleAlert className="size-3.5" aria-hidden="true" />
                            {dashboardT("staleWarning")}
                          </span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TooltipProvider>
          </div>
          <div className="grid gap-3 md:hidden">
            {visibleChains.map((chain) => (
              <ScreenerCard key={chain.slug} chain={chain} />
            ))}
          </div>
        </>
      )}
    </DashboardFrame>
  );
}