"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { ContentTable } from "@/components/marketing/content-table";
import { getMethodology } from "@/lib/public-api/client";
import { publicQueryKeys } from "@/lib/public-api/query-keys";

const PILLARS = [
  { apiName: "adoption", key: "adoption", fallbackWeight: 30 },
  { apiName: "capital", key: "capital", fallbackWeight: 30 },
  { apiName: "security_economics", key: "security_economics", fallbackWeight: 10 },
  { apiName: "market_condition", key: "market_condition", fallbackWeight: 30 },
] as const;

const COVERAGE = [
  { chain: "btc", value: "0.70" },
  { chain: "eth", value: "0.90" },
  { chain: "sol", value: "0.60" },
  { chain: "bnb", value: "0.60" },
] as const;

const SOURCE_KEYS = [
  "binance",
  "defillama",
  "coinMetrics",
  "coingecko",
  "mempool",
  "blockchain",
] as const;

const FLAG_KEYS = [
  "deep_drawdown",
  "high_volatility",
  "liquidity_drying",
  "usage_decline",
  "tvl_outflow",
  "stablecoin_contraction",
  "hashrate_decline",
  "low_confidence",
] as const;

const TOC_KEYS = [
  "about",
  "sources",
  "healthScore",
  "regimes",
  "scenarios",
  "research",
  "assistant",
  "limitations",
] as const;

function latin(value: number | string) {
  return typeof value === "number"
    ? value.toLocaleString("en-US", { useGrouping: false })
    : value;
}

export function MethodologyPage() {
  const locale = useLocale();
  const t = useTranslations("methodologyPage");
  const footer = useTranslations("siteFooter");
  const methodologyQuery = useQuery({
    queryKey: publicQueryKeys.methodology,
    queryFn: getMethodology,
    staleTime: 5 * 60 * 1000,
  });
  const apiPillars = methodologyQuery.data?.pillars;
  const rows = PILLARS.map((pillar) => ({
    key: pillar.key,
    name: t(`sections.healthScore.pillars.${pillar.key}`),
    weight:
      apiPillars?.find((item) => item.name === pillar.apiName)?.weight ??
      pillar.fallbackWeight,
  }));
  const direction = locale === "fa" ? "rtl" : "ltr";

  return (
    <main
      lang={locale}
      dir={direction}
      className="mx-auto max-w-3xl space-y-10 px-4 py-10 sm:px-6 sm:py-14"
    >
      <header className="space-y-4">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          {t("title")}
        </h1>
        <p className="leading-7 text-muted">{t("intro")}</p>
      </header>

      <nav
        aria-label={t("tocLabel")}
        className="rounded-xl border border-border bg-surface p-5"
      >
        <h2 className="font-semibold">{t("tocLabel")}</h2>
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {TOC_KEYS.map((key) => (
            <li key={key}>
              <a className="text-primary underline-offset-4 hover:underline" href={`#${key === "healthScore" ? "health-score" : key}`}>
                {t(`toc.${key}`)}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <section id="about" className="scroll-mt-24 space-y-3">
        <h2 className="text-2xl font-semibold">{t("sections.about.title")}</h2>
        <p className="leading-7 text-muted">{t("sections.about.body")}</p>
      </section>

      <section id="sources" className="scroll-mt-24 space-y-4">
        <h2 className="text-2xl font-semibold">{t("sections.sources.title")}</h2>
        <p className="leading-7 text-muted">{t("sections.sources.intro")}</p>
        <ContentTable
          caption={t("sections.sources.tableCaption")}
          headings={[
            t("sections.sources.sourceHeading"),
            t("sections.sources.useHeading"),
          ]}
        >
          {SOURCE_KEYS.map((key) => (
            <tr key={key} className="align-top">
              <td className="px-3 py-3 font-medium">
                {footer(`sourceNames.${key}`)}
              </td>
              <td className="px-3 py-3 leading-6 text-muted">
                {t(`sections.sources.${key}`)}
              </td>
            </tr>
          ))}
        </ContentTable>
        <h3 className="text-lg font-semibold">
          {t("sections.sources.availabilityHeading")}
        </h3>
        <ul className="list-disc space-y-2 ps-6 leading-6 text-muted">
          <li>{t("sections.sources.available")}</li>
          <li>{t("sections.sources.unverified")}</li>
          <li>{t("sections.sources.notAvailable")}</li>
          <li>{t("sections.sources.discontinued")}</li>
          <li>{t("sections.sources.notApplicable")}</li>
        </ul>
        <p className="leading-7 text-muted">{t("sections.sources.derivedNote")}</p>
        <p className="leading-7 text-muted">{t("sections.sources.coverageNote")}</p>
      </section>

      <section id="health-score" className="scroll-mt-24 space-y-4">
        <h2 className="text-2xl font-semibold">
          {t("sections.healthScore.title")}{" "}
          <code dir="ltr">v1</code>
        </h2>
        <p className="leading-7 text-muted">
          {t("sections.healthScore.intro")}
        </p>
        <ContentTable
          caption={t("sections.healthScore.weightCaption")}
          headings={[
            t("sections.healthScore.pillarHeading"),
            t("sections.healthScore.weightHeading"),
          ]}
        >
          {rows.map((row) => (
            <tr key={row.key}>
              <th scope="row" className="px-3 py-3 text-start font-medium">
                {row.name}
              </th>
              <td className="px-3 py-3">
                <span dir="ltr">{latin(row.weight)}</span>
              </td>
            </tr>
          ))}
        </ContentTable>
        {methodologyQuery.isError && (
          <p className="text-sm text-muted" role="status">
            {t("sections.healthScore.fallbackNote")}
          </p>
        )}
        <p className="leading-7 text-muted">
          {t("sections.healthScore.percentile")}
        </p>
        <ContentTable
          caption={t("sections.healthScore.confidenceCaption")}
          headings={[
            t("sections.healthScore.coverageHeading"),
            t("sections.healthScore.maximumHeading"),
          ]}
        >
          {COVERAGE.map((item) => (
            <tr key={item.chain}>
              <th scope="row" className="px-3 py-3 text-start font-medium">
                {t(`sections.healthScore.chains.${item.chain}`)}
              </th>
              <td className="px-3 py-3">
                <span dir="ltr">{item.value}</span>
              </td>
            </tr>
          ))}
        </ContentTable>
        <p className="leading-7 text-muted">
          {t("sections.healthScore.coverageMaximumIntro")}
        </p>
        <ul className="list-disc space-y-2 ps-6 leading-6 text-muted">
          <li>
            {t("sections.healthScore.confidenceHigh", { value: "0.80" })}
          </li>
          <li>
            {t("sections.healthScore.confidenceMedium", { value: "0.50" })}
          </li>
          <li>{t("sections.healthScore.confidenceLow")}</li>
        </ul>
        <p className="leading-7 text-muted">
          {t("sections.healthScore.minimumCoverage", { value: "0.40" })}
        </p>
        <p className="leading-7 text-muted">
          {t("sections.healthScore.partial")}
        </p>
        <p className="text-sm text-muted">
          {t("sections.healthScore.partialField")}{" "}
          <code dir="ltr">last_full_coverage</code>
        </p>
      </section>

      <section id="regimes" className="scroll-mt-24 space-y-4">
        <h2 className="text-2xl font-semibold">{t("sections.regimes.title")}</h2>
        <p className="leading-7 text-muted">{t("sections.regimes.intro")}</p>
        <ContentTable
          caption={t("sections.regimes.regimeCaption")}
          headings={[
            t("sections.regimes.regimeHeading"),
            t("sections.regimes.conditionHeading"),
          ]}
        >
          {(["stress", "uptrend", "downtrend", "range"] as const).map((key) => (
            <tr key={key}>
              <th scope="row" className="px-3 py-3 text-start font-medium">
                <code dir="ltr">{key}</code>
              </th>
              <td className="px-3 py-3">
                <code dir="ltr" className="whitespace-nowrap">
                  {t(`sections.regimes.${key}`)}
                </code>
              </td>
            </tr>
          ))}
        </ContentTable>
        <p className="leading-7 text-muted">{t("sections.regimes.hysteresis")}</p>
        <p className="leading-7 text-muted">
          {t.rich("sections.regimes.volatility", {
            state: (chunks) => <code dir="ltr">{chunks}</code>,
            metric: (chunks) => <code dir="ltr">{chunks}</code>,
            high: (chunks) => <code dir="ltr">{chunks}</code>,
            low: (chunks) => <code dir="ltr">{chunks}</code>,
            normal: (chunks) => <code dir="ltr">{chunks}</code>,
          })}
        </p>
        <ContentTable
          caption={t("sections.regimes.flagsCaption")}
          headings={[
            t("sections.regimes.flagHeading"),
            t("sections.regimes.ruleHeading"),
          ]}
        >
          {FLAG_KEYS.map((key) => (
            <tr key={key}>
              <th scope="row" className="px-3 py-3 text-start font-medium">
                {t(`sections.regimes.flagNames.${key}`)}
              </th>
              <td className="px-3 py-3">
                <code dir="ltr">{t(`sections.regimes.flagRules.${key}`)}</code>
              </td>
            </tr>
          ))}
        </ContentTable>
      </section>

      <section id="scenarios" className="scroll-mt-24 space-y-4">
        <h2 className="text-2xl font-semibold">
          {t("sections.scenarios.title")}{" "}
          <code dir="ltr">scenarios-v1</code>
        </h2>
        <p className="leading-7 text-muted">
          {t.rich("sections.scenarios.intro", {
            method: (chunks) => <code dir="ltr">{chunks}</code>,
            quantiles: (chunks) => <code dir="ltr">{chunks}</code>,
          })}
        </p>
        <p className="leading-7 text-muted">{t("sections.scenarios.sample")}</p>
        <p className="leading-7 text-muted">
          {t.rich("sections.scenarios.independence", {
            count: (chunks) => <code dir="ltr">{chunks}</code>,
            lowSample: (chunks) => <code dir="ltr">{chunks}</code>,
          })}
        </p>
        <p>
          <code dir="ltr" className="rounded bg-surface px-2 py-1">
            {t("sections.scenarios.formula")}
          </code>
        </p>
        <p className="font-semibold">{t("sections.scenarios.note")}</p>
      </section>

      <section id="research" className="scroll-mt-24 space-y-4">
        <h2 className="text-2xl font-semibold">
          {t("sections.research.title")}
        </h2>
        <p className="leading-7 text-muted">{t("sections.research.intro")}</p>
        <ul className="list-disc space-y-2 ps-6 leading-7 text-muted">
          <li>
            {t.rich("sections.research.shortHorizon", {
              band: (chunks) => <code dir="ltr">{chunks}</code>,
              rate: (chunks) => <span dir="ltr">{chunks}</span>,
            })}
          </li>
          <li>{t("sections.research.longHorizon")}</li>
          <li>{t("sections.research.scoreAssociation")}</li>
          <li>{t("sections.research.regimes")}</li>
        </ul>
        <p className="text-sm text-muted">
          {t.rich("sections.research.commit", {
            hash: "bc6c6f2",
            id: (chunks) => <code dir="ltr">{chunks}</code>,
          })}{" "}
          <a
            href="https://github.com/parhammalekpour/chaincompass/blob/bc6c6f2/docs/RESEARCH.md"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary underline-offset-4 hover:underline"
          >
            {t("sections.research.reportLink")}
          </a>
        </p>
      </section>

      <section id="assistant" className="scroll-mt-24 space-y-3">
        <h2 className="text-2xl font-semibold">
          {t("sections.assistant.title")}
        </h2>
        <p className="leading-7 text-muted">
          {t("sections.assistant.body")}
        </p>
      </section>

      <section id="limitations" className="scroll-mt-24 space-y-4">
        <h2 className="text-2xl font-semibold">
          {t("sections.limitations.title")}
        </h2>
        <ul className="list-disc space-y-2 ps-6 leading-7 text-muted">
          <li>{t("sections.limitations.coverage")}</li>
          <li>{t("sections.limitations.history")}</li>
          <li>{t("sections.limitations.providers")}</li>
          <li>{t("sections.limitations.scope")}</li>
        </ul>
      </section>
    </main>
  );
}
