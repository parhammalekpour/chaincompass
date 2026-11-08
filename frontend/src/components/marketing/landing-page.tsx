import {
  ArrowDownLeft,
  ArrowUpRight,
  BellRing,
  ChartNoAxesCombined,
  Compass,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export async function LandingPage() {
  const t = await getTranslations("landingV1");

  return (
    <main>
      <section className="relative isolate overflow-hidden">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,var(--color-primary)/12%,transparent_60%)] motion-safe:animate-pulse motion-reduce:animate-none" />
        <div className="mx-auto grid max-w-7xl items-center gap-12 px-4 py-16 sm:px-6 sm:py-24 lg:grid-cols-2 lg:py-28">
          <div className="space-y-7">
            <p className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 text-sm text-muted">
              <Compass className="size-4 text-primary" aria-hidden="true" />
              {t("eyebrow")}
            </p>
            <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
              {t("headline")}
            </h1>
            <p className="max-w-2xl text-lg leading-8 text-muted">
              {t("subheadline")}
            </p>
            <div className="flex flex-wrap gap-3">
              <Button asChild size="lg">
                <Link href="/register">{t("getStarted")}</Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link href="/methodology">{t("seeMethodology")}</Link>
              </Button>
            </div>
            <p className="text-sm text-muted">{t("supportedChains")}</p>
          </div>

          <ProductPreview
            labels={{
              title: t("previewTitle"),
              score: t("previewScore"),
              status: t("previewStatus"),
              activity: t("previewActivity"),
              risk: t("previewRisk"),
              network: t("previewNetwork"),
              rangeStart: t("previewRangeStart"),
              rangeEnd: t("previewRangeEnd"),
            }}
          />
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20">
        <SectionHeading title={t("featuresTitle")} description={t("featuresDescription")} />
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          <FeatureCard
            icon={<ChartNoAxesCombined aria-hidden="true" />}
            title={t("healthTitle")}
            description={t("healthDescription")}
          />
          <FeatureCard
            icon={<BellRing aria-hidden="true" />}
            title={t("alertsTitle")}
            description={t("alertsDescription")}
          />
          <FeatureCard
            icon={<Sparkles aria-hidden="true" />}
            title={t("analystTitle")}
            description={t("analystDescription")}
          />
        </div>
      </section>

      <section className="border-y border-border bg-surface/40">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20">
          <SectionHeading title={t("howTitle")} description={t("howDescription")} />
          <ol className="mt-10 grid gap-6 md:grid-cols-3">
            {[1, 2, 3].map((step) => (
              <li key={step} className="space-y-3">
                <span className="inline-flex size-10 items-center justify-center rounded-full border border-primary/40 bg-primary/10 font-semibold text-primary">
                  {step}
                </span>
                <h3 className="text-lg font-semibold">{t(`step${step}Title`)}</h3>
                <p className="leading-7 text-muted">{t(`step${step}Description`)}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20">
        <SectionHeading title={t("promiseTitle")} description={t("promiseDescription")} />
        <div className="mt-8 grid gap-3 md:grid-cols-3">
          {[1, 2, 3].map((promise) => (
            <div key={promise} className="flex items-start gap-3 rounded-xl border border-border bg-surface p-5">
              <ShieldCheck className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />
              <p className="leading-7">{t(`promise${promise}`)}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-6 sm:pb-20">
        <div className="rounded-2xl border border-warning/30 bg-warning/5 p-6 sm:p-8">
          <h2 className="font-semibold">{t("disclaimerTitle")}</h2>
          <p className="mt-2 max-w-4xl leading-7 text-muted">{t("disclaimer")}</p>
        </div>
        <div className="mt-8 flex flex-col items-start justify-between gap-5 rounded-2xl bg-primary p-6 text-primary-foreground sm:flex-row sm:items-center sm:p-8">
          <div>
            <h2 className="text-2xl font-semibold">{t("finalTitle")}</h2>
            <p className="mt-2 max-w-2xl leading-7 opacity-85">{t("finalDescription")}</p>
          </div>
          <Button asChild variant="secondary" size="lg">
            <Link href="/register">{t("getStarted")}</Link>
          </Button>
        </div>
      </section>
    </main>
  );
}

function SectionHeading({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="max-w-2xl space-y-3">
      <h2 className="text-3xl font-semibold tracking-tight">{title}</h2>
      <p className="leading-7 text-muted">{description}</p>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <Card className="transition-colors motion-safe:duration-200 hover:border-primary/40">
      <CardContent className="space-y-4 p-6">
        <span className="inline-flex size-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
          {icon}
        </span>
        <h3 className="text-lg font-semibold">{title}</h3>
        <p className="leading-7 text-muted">{description}</p>
      </CardContent>
    </Card>
  );
}

function ProductPreview({
  labels,
}: {
  labels: Record<string, string>;
}) {
  return (
    <Card className="overflow-hidden border-border bg-surface shadow-2xl shadow-black/20">
      <div className="flex items-center justify-between border-b border-border p-5">
        <div className="flex items-center gap-3">
          <span className="inline-flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Compass aria-hidden="true" />
          </span>
          <div>
            <p className="font-semibold">{labels.title}</p>
            <p className="mt-1 text-xs text-muted">{labels.network}</p>
          </div>
        </div>
        <span className="rounded-full border border-success/30 bg-success/10 px-3 py-1 text-xs text-success">
          {labels.status}
        </span>
      </div>
      <CardContent className="space-y-5 p-5">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-border bg-background p-4">
            <p className="text-sm text-muted">{labels.score}</p>
            <p dir="ltr" className="mt-2 text-3xl font-semibold tabular-nums">82<span className="text-base text-muted">/100</span></p>
          </div>
          <div className="rounded-xl border border-border bg-background p-4">
            <p className="text-sm text-muted">{labels.risk}</p>
            <p className="mt-3 text-lg font-medium">{labels.status}</p>
          </div>
        </div>
        <div className="rounded-xl border border-border bg-background p-4">
          <div className="flex items-center justify-between gap-4">
            <p className="text-sm text-muted">{labels.activity}</p>
            <span dir="ltr" className="inline-flex items-center gap-1 text-sm text-success">
              <ArrowUpRight className="size-4" aria-hidden="true" />
              4.8%
            </span>
          </div>
          <div className="mt-5 flex h-20 items-end gap-2" aria-hidden="true">
            {[38, 55, 45, 70, 58, 84, 66, 92, 75, 100, 79, 88].map((height, index) => (
              <span
                key={index}
                className={cn(
                  "flex-1 rounded-t-sm bg-primary/50 motion-safe:transition-all motion-safe:duration-500",
                  index > 8 && "bg-primary",
                )}
                style={{ height: `${height}%` }}
              />
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-muted">
            <span>{labels.rangeStart}</span>
            <ArrowDownLeft className="size-3" aria-hidden="true" />
            <span>{labels.rangeEnd}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
