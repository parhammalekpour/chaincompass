"use client";

import { useTranslations } from "next-intl";
import { PageSkeleton } from "@/components/states/page-skeleton";

export function PlaceholderPage({
  namespace,
  compact = false,
  values,
}: {
  namespace: string;
  compact?: boolean;
  values?: Record<string, string>;
}) {
  const t = useTranslations(namespace);

  return (
    <section className={compact ? "space-y-5" : "mx-auto max-w-6xl space-y-6"}>
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title", values)}</h1>
        <p className="text-muted">{t("description", values)}</p>
      </div>
      <PageSkeleton />
    </section>
  );
}
