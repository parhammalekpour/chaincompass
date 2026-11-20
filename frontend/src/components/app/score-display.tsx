"use client";

import { useTranslations } from "next-intl";
import type { ChainSummary } from "@/lib/public-api/contracts";
import { formatScore } from "@/lib/dashboard-data";

type Confidence = NonNullable<ChainSummary["score"]>["confidence_label"];
const confidenceKeys: Record<Confidence, "high" | "medium" | "low"> = {
  High: "high",
  Medium: "medium",
  Low: "low",
};

export function ConfidenceBadge({ label }: { label: Confidence }) {
  const t = useTranslations("dashboard.confidence");
  return (
    <span className="inline-flex rounded-full border border-border bg-muted/40 px-2 py-0.5 text-xs text-muted">
      {t(confidenceKeys[label])}
    </span>
  );
}

export function ScoreDisplay({
  score,
}: {
  score: ChainSummary["score"];
}) {
  const t = useTranslations("dashboard");
  if (!score) {
    return (
      <p className="text-sm text-muted" data-testid="score-unavailable">
        {t("notEnoughHistory")}
      </p>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span dir="ltr" className="tabular-nums text-xl font-semibold">
        {formatScore(score.value)} /100
      </span>
      <ConfidenceBadge label={score.confidence_label} />
    </div>
  );
}