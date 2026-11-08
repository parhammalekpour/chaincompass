"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { useTranslations } from "next-intl";

export function PageSkeleton() {
  const t = useTranslations("states");

  return (
    <div
      role="status"
      aria-label={t("loading")}
      className="space-y-5"
    >
      <span className="sr-only">{t("loading")}</span>
      <div className="grid gap-4 sm:grid-cols-3">
        {["one", "two", "three"].map((item) => (
          <div key={item} className="space-y-3 rounded-xl border border-border p-5">
            <Skeleton className="h-4 w-2/5" />
            <Skeleton className="h-8 w-3/5" />
            <Skeleton className="h-3 w-4/5" />
          </div>
        ))}
      </div>
      <Skeleton className="h-56 w-full rounded-xl" />
    </div>
  );
}
