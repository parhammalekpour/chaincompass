"use client";

import { AlertTriangle, CircleAlert, Info } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { Link } from "@/i18n/navigation";
import type {
  ChainDetailResponse,
  ChainSummary,
} from "@/lib/public-api/contracts";
import { formatCoverage, formatScore } from "@/lib/dashboard-data";
import { chainNameKeys } from "@/components/app/chain-labels";
import { PriceValue, ReturnValue } from "@/components/app/return-value";
import { ScoreDisplay } from "@/components/app/score-display";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const knownFlags = [
  "deep_drawdown",
  "high_volatility",
  "liquidity_drying",
  "usage_decline",
  "tvl_outflow",
  "stablecoin_contraction",
] as const;

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

function SeverityIcon({ severity }: { severity: string }) {
  const Icon =
    severity === "high"
      ? AlertTriangle
      : severity === "low"
        ? Info
        : CircleAlert;
  return <Icon className="size-3.5 text-muted" aria-hidden="true" />;
}

type LastFullCoverage = ChainDetailResponse["last_full_coverage"];

function PartialBadge({
  chain,
  lastFullCoverage,
  isLoading,
  isError,
}: {
  chain: ChainSummary;
  lastFullCoverage: LastFullCoverage;
  isLoading: boolean;
  isError: boolean;
}) {
  const t = useTranslations("dashboard");
  const score = chain.score;
  if (!score?.is_partial) return null;

  const tooltip = t.rich("partialTooltip", {
    ltr: (chunks) => (
      <bdi dir="ltr" className="tabular-nums">{chunks}</bdi>
    ),
    coverage: formatCoverage(score.coverage),
    coverageMax: formatCoverage(score.coverage_max),
  });
  let historyText: ReactNode;
  if (lastFullCoverage) {
    historyText = t.rich("lastFullCoverage", {
      ltr: (chunks) => (
        <bdi dir="ltr" className="tabular-nums">{chunks}</bdi>
      ),
      value: formatScore(lastFullCoverage.value),
      date: lastFullCoverage.as_of_date,
    });
  } else if (isLoading) {
    historyText = t("lastFullLoading");
  } else if (isError) {
    historyText = t("lastFullError");
  } else {
    historyText = t("lastFullUnavailable");
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="outline"
          size="xs"
          aria-label={t("partialDetails")}
          className="gap-1"
        >
          <Info aria-hidden="true" />
          {t("partial")}
        </Button>
      </TooltipTrigger>
      <TooltipContent className="max-w-sm whitespace-normal leading-5">
        <span>{tooltip} </span>
        <span>{historyText}</span>
      </TooltipContent>
    </Tooltip>
  );
}

export function ChainCard({
  chain,
  lastFullCoverage,
  isLastFullCoverageLoading = false,
  isLastFullCoverageError = false,
}: {
  chain: ChainSummary;
  lastFullCoverage?: LastFullCoverage;
  isLastFullCoverageLoading?: boolean;
  isLastFullCoverageError?: boolean;
}) {
  const t = useTranslations("dashboard");
  const chainName = t(chainNameKeys[chain.slug]);
  const visibleFlags = chain.flags.slice(0, 3);
  const remainingFlags = chain.flags.slice(3);

  return (
    <TooltipProvider>
      <Card size="sm" className="h-full">
        <CardHeader className="gap-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <CardTitle className="text-lg">
                <Link
                  href={`/app/chains/${chain.slug}`}
                  className="rounded-sm hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {chainName}
                </Link>
              </CardTitle>
              <p dir="ltr" className="text-xs tracking-wide text-muted">
                {chain.symbol}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {chain.regime && (
                <span className="rounded-full border border-border bg-muted/40 px-2 py-1 text-xs">
                  {t(regimeTranslationKey(chain.regime.label))}
                  <span className="ms-1 text-muted">
                    <span dir="ltr" className="tabular-nums">
                      {new Intl.NumberFormat("en-US").format(
                        chain.regime.days_in_regime,
                      )}
                    </span>{" "}
                    {t("daysCount")}
                  </span>
                </span>
              )}
              {chain.regime?.vol_state && (
                <span className="rounded-full border border-border bg-muted/40 px-2 py-1 text-xs">
                  {t(volatilityTranslationKey(chain.regime.vol_state))}
                </span>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ScoreDisplay score={chain.score} />
            <PartialBadge
              chain={chain}
              lastFullCoverage={lastFullCoverage}
              isLoading={isLastFullCoverageLoading}
              isError={isLastFullCoverageError}
            />
          </div>
          {chain.score && (
            <p className="text-xs text-muted">
              {t.rich("coverage", {
                ltr: (chunks) => (
                  <bdi dir="ltr" className="tabular-nums">{chunks}</bdi>
                ),
                coverage: formatCoverage(chain.score.coverage),
                coverageMax: formatCoverage(chain.score.coverage_max),
              })}
            </p>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div className="space-y-1">
              <dt className="text-xs text-muted">{t("price")}</dt>
              <dd><PriceValue value={chain.price.close_usd} /></dd>
            </div>
            <div className="space-y-1">
              <dt className="text-xs text-muted">{t("return30d")}</dt>
              <dd><ReturnValue value={chain.price.ret_30d} /></dd>
            </div>
          </dl>
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted">{t("activeFlags")}</p>
            {chain.flags.length === 0 ? (
              <p className="text-xs text-muted">{t("noActiveFlags")}</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {visibleFlags.map((flag) => (
                  <span
                    key={`${flag.flag}-${flag.severity}`}
                    className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-1 text-xs"
                    aria-label={`${t(flagTranslationKey(flag.flag))}, ${t(severityTranslationKey(flag.severity))}`}
                  >
                    <SeverityIcon severity={flag.severity} />
                    {t(flagTranslationKey(flag.flag))}
                  </span>
                ))}
                {remainingFlags.length > 0 && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button variant="outline" size="xs">
                        +{remainingFlags.length} {t("more")}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-sm whitespace-normal">
                      <ul className="space-y-1">
                        {remainingFlags.map((flag) => (
                          <li
                            key={`${flag.flag}-${flag.severity}`}
                            className="flex items-center gap-1.5"
                          >
                            <SeverityIcon severity={flag.severity} />
                            <span>{t(flagTranslationKey(flag.flag))}</span>
                            <span>({t(severityTranslationKey(flag.severity))})</span>
                          </li>
                        ))}
                      </ul>
                    </TooltipContent>
                  </Tooltip>
                )}
              </div>
            )}
          </div>
          <div className="flex items-start gap-2 border-t border-border pt-3 text-xs text-muted">
            {chain.freshness.stale ? (
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            ) : null}
            <p>
              <span>{t("priceDataPrefix")} </span>
              {chain.freshness.price_last_date ?? chain.price.as_of_date ? (
                <time
                  dir="ltr"
                  dateTime={
                    chain.freshness.price_last_date ??
                    chain.price.as_of_date ??
                    undefined
                  }
                >
                  {chain.freshness.price_last_date ?? chain.price.as_of_date}
                </time>
              ) : (
                t("notAvailable")
              )}
              {chain.freshness.stale && (
                <span className="ms-1">{t("staleWarning")}</span>
              )}
            </p>
          </div>
        </CardContent>
      </Card>
    </TooltipProvider>
  );
}