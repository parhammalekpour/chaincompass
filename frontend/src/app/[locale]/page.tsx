import { hasLocale } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { Num } from "@/components/num";
import { SiteControls } from "@/components/site-controls";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { routing } from "@/i18n/routing";
import type { AppLocale } from "@/lib/format";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }
  setRequestLocale(locale);

  const t = await getTranslations("landing");
  const common = await getTranslations("common");
  const appLocale = locale as AppLocale;

  return (
    <main className="mx-auto flex min-h-svh w-full max-w-6xl flex-col px-6 py-8 sm:px-10">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-6">
        <span className="text-lg font-semibold tracking-tight text-primary">
          {common("appName")}
        </span>
        <SiteControls />
      </header>

      <section className="grid flex-1 items-center gap-12 py-16 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          <p className="text-sm font-semibold tracking-wide text-primary">
            {t("eyebrow")}
          </p>
          <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
            {t("title")}
          </h1>
          <p className="max-w-2xl text-lg leading-8 text-muted">
            {t("description")}
          </p>
          <p className="text-sm text-muted">{t("scope")}</p>
          <p className="max-w-2xl border-s-2 border-primary ps-4 text-sm leading-6 text-muted">
            {t("disclaimer")}
          </p>
        </div>

        <Card className="border-border bg-surface shadow-xl shadow-black/10">
          <CardHeader>
            <CardTitle>{t("sampleHeading")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <Metric label={common("sampleNumber")}>
              <Num value={9876} locale={appLocale} format="compact" />
            </Metric>
            <Metric label={common("sampleCurrency")}>
              <Num value={42850.75} locale={appLocale} format="currency" />
            </Metric>
            <Metric label={common("samplePercent")}>
              <Num value={0.034} locale={appLocale} format="percent" />
            </Metric>
            <p className="text-xs leading-5 text-muted">{t("sampleNote")}</p>
          </CardContent>
        </Card>
      </section>
    </main>
  );
}

function Metric({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border pb-4 last:border-b-0 last:pb-0">
      <span className="text-sm text-muted">{label}</span>
      <span className="text-lg font-semibold tabular-nums">{children}</span>
    </div>
  );
}
