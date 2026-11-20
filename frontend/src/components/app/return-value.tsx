"use client";

import { useTranslations } from "next-intl";
import { formatCompactUsd, formatSignedPercent } from "@/lib/dashboard-data";
import type { ChainSummary } from "@/lib/public-api/contracts";

export function PriceValue({ value }: { value: string | null }) {
  const t = useTranslations("dashboard");
  return (
    <span dir="ltr" className="tabular-nums">
      {value === null ? t("notAvailable") : formatCompactUsd(value)}
    </span>
  );
}

export function ReturnValue({
  value,
}: {
  value: ChainSummary["price"]["ret_30d"];
}) {
  const t = useTranslations("dashboard");
  if (value === null) {
    return (
      <span dir="ltr" className="tabular-nums">
        {t("notAvailable")}
      </span>
    );
  }
  const numeric = Number(value);
  const direction = numeric > 0 ? "up" : numeric < 0 ? "down" : "flat";
  const arrow = direction === "up" ? "↑" : direction === "down" ? "↓" : "→";
  const color =
    direction === "up"
      ? "text-success"
      : direction === "down"
        ? "text-danger"
        : "text-foreground";

  return (
    <span dir="ltr" className={`tabular-nums ${color}`}>
      {formatSignedPercent(value)} {arrow}
    </span>
  );
}