"use client";

import {
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  CircleAlert,
  CircleCheck,
  CircleHelp,
  Info,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { Fragment } from "react";
import { Link } from "@/i18n/navigation";
import { chainNameKeys } from "@/components/app/chain-labels";
import { ConfidenceBadge } from "@/components/app/score-display";
import { ChainNotFoundPage } from "@/components/chains/chain-detail-page";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import { PublicApiErrorState } from "@/components/states/public-api-error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/public-api/client";
import type {
  ChainSlug,
  FundamentalReportResponse,
  ReportIndicatorStatus,
} from "@/lib/public-api/contracts";
import { useFundamentalReport } from "@/hooks/use-fundamental-report";
import { formatCoverage, formatScore } from "@/lib/dashboard-data";

const indicatorGroups = ["market", "capital", "usage", "security"] as const;
const fixedFreeSourceGaps = new Set([
  "holder_distribution",
  "exchange_flows",
  "news_evidence",
]);

function ReportLoading() {
  const locale = useLocale();
  const t = useTranslations("states");
  return (
    <main
      dir={locale === "fa" ? "rtl" : "ltr"}
      role="status"
      aria-label={t("loading")}
      className="mx-auto max-w-6xl min-w-0 space-y-6"
    >
      <Skeleton className="h-8 w-2/3" />
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-56 w-full" />
      <Skeleton className="h-64 w-full" />
    </main>
  );
}

function SignedChange({
  value,
  label,
  previousScore,
  previousLabel,
  testId,
}: {
  value: string | null;
  label: string;
  previousScore: string | null;
  previousLabel: string;
  testId: string;
}) {
  const t = useTranslations("fundamentalReport");
  if (value === null) {
    return (
      <div className="space-y-2 rounded-lg border border-border p-3">
        <p className="text-sm text-muted">{label}</p>
        <p className="text-sm">{t("insufficientHistory")}</p>
      </div>
    );
  }

  const zero = /^-?0+(?:\.0+)?$/.test(value);
  const Icon = zero ? ArrowRight : value.startsWith("-") ? ArrowDown : ArrowUp;
  const signedValue = value.startsWith("-") ? value : `+${value}`;

  return (
    <div className="space-y-2 rounded-lg border border-border p-3">
      <p className="text-sm text-muted">{label}</p>
      <p
        data-testid={testId}
        className="inline-flex items-center gap-2 text-sm text-muted"
      >
        <Icon aria-hidden="true" className="size-4" />
        <bdi dir="ltr" className="tabular-nums">
          {signedValue}
        </bdi>
      </p>
      {previousScore !== null && (
        <p className="text-xs text-muted">
          {previousLabel}:{" "}
          <bdi dir="ltr" className="tabular-nums">
            {formatScore(previousScore)}
          </bdi>
        </p>
      )}
    </div>
  );
}

function IndicatorStatus({
  status,
}: {
  status: ReportIndicatorStatus;
}) {
  const t = useTranslations("fundamentalReport");
  const Icon =
    status === "available"
      ? CircleCheck
      : status === "not_applicable"
        ? CircleHelp
        : CircleAlert;
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted">
      <Icon aria-hidden="true" className="size-4 shrink-0" />
      {t(`statusLabels.${status}`)}
    </span>
  );
}

function ReportNotAvailable({ slug }: { slug: ChainSlug }) {
  const locale = useLocale();
  const t = useTranslations("fundamentalReport");
  const errorT = useTranslations("publicErrors");
  const dashboardT = useTranslations("dashboard");
  const chainName = dashboardT(chainNameKeys[slug]);

  return (
    <main
      dir={locale === "fa" ? "rtl" : "ltr"}
      className="mx-auto max-w-6xl min-w-0"
    >
      <section
        role="status"
        className="mx-auto max-w-xl rounded-xl border border-border bg-card p-6 text-center"
      >
        <h1 className="text-xl font-semibold">{t("title")}</h1>
        <p className="mt-2 text-sm text-muted">
          {errorT("reportNotAvailable")}
        </p>
        <Button asChild className="mt-5" variant="outline">
          <Link href={`/app/chains/${slug}`}>{t("backToChain", { chainName })}</Link>
        </Button>
      </section>
    </main>
  );
}

function regimeLabel(
  value: string | null,
  dashboardT: ReturnType<typeof useTranslations>,
  reportT: ReturnType<typeof useTranslations>,
) {
  if (value === null) return reportT("notAvailable");
  if (value === "uptrend" || value === "downtrend" || value === "range") {
    return dashboardT(`regimes.${value}`);
  }
  return value;
}

function volatilityLabel(
  value: string | null,
  dashboardT: ReturnType<typeof useTranslations>,
  reportT: ReturnType<typeof useTranslations>,
) {
  if (value === null) return reportT("notAvailable");
  if (value === "low" || value === "normal" || value === "high") {
    return dashboardT(`volatility.${value}`);
  }
  return value;
}

function FlagsSection({
  report,
}: {
  report: FundamentalReportResponse;
}) {
  const t = useTranslations("fundamentalReport");

  return (
    <section className="space-y-3" aria-labelledby="fundamental-report-flags">
      <h2 id="fundamental-report-flags" className="text-xl font-semibold">
        {t("flags")}
      </h2>
      <Card>
        <CardContent className="pt-4">
          {report.flags.length === 0 ? (
            <p className="text-sm text-muted">{t("noActiveFlags")}</p>
          ) : (
            <ul className="space-y-3">
              {report.flags.map((flag, index) => {
                const Icon =
                  flag.severity === "high"
                    ? AlertTriangle
                    : flag.severity === "medium"
                      ? CircleAlert
                      : Info;
                return (
                  <li
                    key={`${flag.code}-${index}`}
                    className="flex flex-wrap items-center gap-x-3 gap-y-1"
                  >
                    <Icon
                      aria-hidden="true"
                      className="size-4 shrink-0 text-muted"
                    />
                    <code dir="ltr" className="break-all">
                      {flag.code}
                    </code>
                    <span className="text-sm text-muted">
                      {t("severity")}:{" "}
                      {t(`severityLabels.${flag.severity}`)}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

function IndicatorsSection({
  report,
}: {
  report: FundamentalReportResponse;
}) {
  const t = useTranslations("fundamentalReport");

  return (
    <section
      className="min-w-0 space-y-3"
      aria-labelledby="fundamental-report-indicators"
    >
      <h2
        id="fundamental-report-indicators"
        className="text-xl font-semibold"
      >
        {t("indicators")}
      </h2>
      <Card className="min-w-0">
        <CardContent className="min-w-0 space-y-4 pt-4">
          <p className="text-sm text-muted">{t("rawValueNote")}</p>
          <div className="min-w-0 max-w-full overflow-x-auto">
            <table className="w-full min-w-[36rem] table-fixed border-collapse text-sm">
              <caption className="caption-bottom p-2 text-start text-xs text-muted">
                {t("indicatorTableCaption")}
              </caption>
              <thead>
                <tr className="border-b border-border">
                  <th scope="col" className="px-3 py-2 text-start font-medium">
                    {t("indicator")}
                  </th>
                  <th scope="col" className="px-3 py-2 text-start font-medium">
                    {t("value")}
                  </th>
                  <th scope="col" className="px-3 py-2 text-start font-medium">
                    {t("percentile")}
                  </th>
                  <th scope="col" className="px-3 py-2 text-start font-medium">
                    {t("status")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {indicatorGroups.map((group) => {
                  const indicators = report.indicators.filter(
                    (indicator) => indicator.group === group,
                  );
                  if (indicators.length === 0) return null;
                  return (
                    <Fragment key={group}>
                      <tr className="border-b border-border">
                        <th
                          scope="rowgroup"
                          colSpan={4}
                          className="bg-muted/30 px-3 py-2 text-start font-medium"
                        >
                          {t(`groupNames.${group}`)}
                        </th>
                      </tr>
                      {indicators.map((indicator) => (
                        <tr
                          key={indicator.key}
                          className="border-b border-border/70"
                        >
                          <th
                            scope="row"
                            className="break-all px-3 py-3 text-start font-normal"
                          >
                            <code dir="ltr">{indicator.key}</code>
                          </th>
                          <td className="px-3 py-3">
                            {indicator.value === null ? (
                              <span className="text-muted">
                                {t("notAvailable")}
                              </span>
                            ) : (
                              <bdi
                                dir="ltr"
                                className="whitespace-nowrap tabular-nums"
                              >
                                {indicator.value}
                              </bdi>
                            )}
                          </td>
                          <td className="px-3 py-3">
                            {indicator.percentile === null ? (
                              <span className="text-muted">
                                {t("notAvailable")}
                              </span>
                            ) : (
                              <bdi
                                dir="ltr"
                                className="whitespace-nowrap tabular-nums"
                              >
                                {formatScore(indicator.percentile)} /100
                              </bdi>
                            )}
                          </td>
                          <td className="px-3 py-3">
                            <IndicatorStatus status={indicator.status} />
                          </td>
                        </tr>
                      ))}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
          {report.indicators.length === 0 && (
            <p className="text-sm text-muted">{t("noIndicators")}</p>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

function DataGapsSection({
  report,
}: {
  report: FundamentalReportResponse;
}) {
  const t = useTranslations("fundamentalReport");

  return (
    <section className="space-y-3" aria-labelledby="fundamental-report-gaps">
      <h2 id="fundamental-report-gaps" className="text-xl font-semibold">
        {t("dataGaps")}
      </h2>
      <Card>
        <CardContent className="pt-4">
          {report.data_gaps.length === 0 ? (
            <p className="text-sm text-muted">{t("noDataGaps")}</p>
          ) : (
            <ul className="space-y-3">
              {report.data_gaps.map((gap, index) => {
                const isFixedFreeSourceGap = fixedFreeSourceGaps.has(gap.key);
                const Icon = isFixedFreeSourceGap ? Info : CircleHelp;
                const label = isFixedFreeSourceGap
                  ? t(`gapNames.${gap.key}`)
                  : gap.key;
                return (
                  <li
                    key={`${gap.key}-${index}`}
                    className="flex flex-wrap items-start gap-x-3 gap-y-1"
                  >
                    <Icon
                      aria-hidden="true"
                      className="mt-0.5 size-4 shrink-0 text-muted"
                    />
                    <span className="min-w-0 space-y-1">
                      <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span>{label}</span>
                        <code dir="ltr" className="break-all text-xs text-muted">
                          {gap.key}
                        </code>
                      </span>
                      <span className="block text-sm text-muted">
                        {isFixedFreeSourceGap
                          ? t("gapStatuses.not_available_free")
                          : t(`gapStatuses.${gap.status}`)}
                      </span>
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

export function FundamentalReportPage({ slug }: { slug: ChainSlug }) {
  const locale = useLocale();
  const t = useTranslations("fundamentalReport");
  const dashboardT = useTranslations("dashboard");
  const reportQuery = useFundamentalReport(slug);

  if (reportQuery.isPending) return <ReportLoading />;
  if (reportQuery.isError) {
    if (
      reportQuery.error instanceof ApiError &&
      reportQuery.error.code === "report_not_available"
    ) {
      return <ReportNotAvailable slug={slug} />;
    }
    if (
      reportQuery.error instanceof ApiError &&
      reportQuery.error.code === "chain_not_found"
    ) {
      return <ChainNotFoundPage />;
    }
    return (
      <main
        dir={locale === "fa" ? "rtl" : "ltr"}
        className="mx-auto max-w-6xl min-w-0"
      >
        <PublicApiErrorState
          error={reportQuery.error}
          onRetry={() => void reportQuery.refetch()}
        />
      </main>
    );
  }

  const report = reportQuery.data;
  const chainName = dashboardT(chainNameKeys[slug]);

  return (
    <main
      dir={locale === "fa" ? "rtl" : "ltr"}
      className="mx-auto max-w-6xl min-w-0 space-y-8"
    >
      <header className="min-w-0 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link
            href={`/app/chains/${slug}`}
            className="text-sm text-muted underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {t("backToChain", { chainName })}
          </Link>
          <span className="text-sm text-muted">
            {t("methodologyVersion")}:{" "}
            <code dir="ltr">{report.methodology_version}</code>
          </span>
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("forChain", { chainName })}
          </h1>
          <p className="text-sm text-muted">
            {t("asOf")}{" "}
            <bdi dir="ltr" className="tabular-nums">
              {report.as_of_date}
            </bdi>
          </p>
          <p className="text-sm text-muted">{t("generatedFromStoredData")}</p>
          <p className="text-sm text-muted">{t("historicalNote")}</p>
        </div>
      </header>

      <section className="space-y-3" aria-labelledby="fundamental-report-health">
        <h2 id="fundamental-report-health" className="text-xl font-semibold">
          {t("health")}
        </h2>
        <Card>
          <CardContent className="space-y-5 pt-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-1">
                <p className="text-sm text-muted">{t("score")}</p>
                <p className="text-xl font-semibold">
                  <bdi dir="ltr" className="tabular-nums">
                    {formatScore(report.health.score)} /100
                  </bdi>
                </p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-muted">{t("confidence")}</p>
                <ConfidenceBadge label={report.health.confidence} />
              </div>
              <div className="space-y-1">
                <p className="text-sm text-muted">{t("coverage")}</p>
                <p>
                  <bdi dir="ltr" className="tabular-nums">
                    {formatCoverage(report.health.coverage)}%
                  </bdi>
                </p>
              </div>
            </div>
            <div className="space-y-3">
              <h3 className="text-sm font-medium">{t("changesTitle")}</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                <SignedChange
                  value={report.health.change_30d}
                  label={t("change30d")}
                  previousScore={report.health.score_30d_ago}
                  previousLabel={t("score30d")}
                  testId="score-change-30d"
                />
                <SignedChange
                  value={report.health.change_90d}
                  label={t("change90d")}
                  previousScore={report.health.score_90d_ago}
                  previousLabel={t("score90d")}
                  testId="score-change-90d"
                />
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-3" aria-labelledby="fundamental-report-regime">
        <h2 id="fundamental-report-regime" className="text-xl font-semibold">
          {t("regime")}
        </h2>
        <Card>
          <CardContent className="grid gap-4 pt-4 sm:grid-cols-2">
            <div className="space-y-1">
              <p className="text-sm text-muted">{t("regime")}</p>
              <p>{regimeLabel(report.regime.regime, dashboardT, t)}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted">{t("volatility")}</p>
              <p>{volatilityLabel(report.regime.vol_state, dashboardT, t)}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted">{t("sinceDate")}</p>
              <p>
                {report.regime.since_date ? (
                  <bdi dir="ltr" className="tabular-nums">
                    {report.regime.since_date}
                  </bdi>
                ) : (
                  t("notAvailable")
                )}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted">{t("daysInRegime")}</p>
              <p>
                {report.regime.days_in_regime === null ? (
                  t("notAvailable")
                ) : (
                  <bdi dir="ltr" className="tabular-nums">
                    {new Intl.NumberFormat("en-US").format(
                      report.regime.days_in_regime,
                    )}
                  </bdi>
                )}
              </p>
            </div>
            {report.regime.history_gap && (
              <p role="note" className="text-sm text-muted sm:col-span-2">
                {t("historyGap")}
              </p>
            )}
          </CardContent>
        </Card>
      </section>

      <FlagsSection report={report} />
      <IndicatorsSection report={report} />
      <DataGapsSection report={report} />

      <div className="flex justify-start">
        <Button asChild>
          <Link href={`/app/chat?ask=report&chain=${slug}`}>
            {t("explainWithAssistant")}
          </Link>
        </Button>
      </div>
    </main>
  );
}
