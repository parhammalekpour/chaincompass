"use client";

import { useTranslations } from "next-intl";
import type { ScenarioHorizon } from "@/lib/public-api/contracts";
import {
  formatPercentShare,
  formatSignedPercent,
} from "@/lib/dashboard-data";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const scenarioNameKeys: Record<
  "pessimistic" | "base" | "optimistic",
  "scenarioNames.pessimistic" | "scenarioNames.base" | "scenarioNames.optimistic"
> = {
  pessimistic: "scenarioNames.pessimistic",
  base: "scenarioNames.base",
  optimistic: "scenarioNames.optimistic",
};

function latinInteger(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(
    value,
  );
}

export function ScenarioHorizonCard({
  horizon,
}: {
  horizon: ScenarioHorizon;
}) {
  const t = useTranslations("chainDetail");
  const insufficientHistory =
    !horizon.available && horizon.reason === "insufficient_history";

  return (
    <Card data-testid={`scenario-horizon-${horizon.days}`} className="h-full">
      <CardHeader>
        <CardTitle>{t("horizonDays", { days: latinInteger(horizon.days) })}</CardTitle>
        {horizon.low_sample && (
          <span className="w-fit rounded-full border border-border bg-muted/40 px-2 py-1 text-xs text-muted">
            {t("lowSample")}
          </span>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {insufficientHistory ? (
          <p className="text-sm text-muted">{t("insufficientHistory")}</p>
        ) : !horizon.available ? (
          <p className="text-sm text-muted">{t("emptyScenarios")}</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-3">
            {horizon.scenarios.map((scenario) => (
              <div
                key={scenario.name}
                className="rounded-lg border border-border px-3 py-2"
              >
                <p className="text-sm text-muted">
                  {t(scenarioNameKeys[scenario.name])}
                </p>
                <p dir="ltr" className="tabular-nums text-lg font-semibold">
                  {formatSignedPercent(scenario.return)}
                </p>
              </div>
            ))}
          </div>
        )}
        {horizon.days === 365 && (
          <p className="text-sm text-muted">{t("calibrationNotAssessed")}</p>
        )}
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted">{t("independentWindows")}</dt>
            <dd dir="ltr" className="tabular-nums">
              {latinInteger(horizon.n_independent)}
            </dd>
          </div>
          {horizon.share_negative !== null && (
            <div>
              <dt className="text-muted">{t("shareNegative")}</dt>
              <dd dir="ltr" className="tabular-nums">
                {formatPercentShare(horizon.share_negative)}
              </dd>
            </div>
          )}
        </dl>
      </CardContent>
    </Card>
  );
}
