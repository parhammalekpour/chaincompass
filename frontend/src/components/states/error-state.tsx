"use client";

import { AlertCircle, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

export function ErrorState({ onRetry }: { onRetry: () => void }) {
  const t = useTranslations("states");

  return (
    <section
      role="alert"
      className="flex flex-col items-center rounded-xl border border-danger/30 bg-danger/5 px-6 py-12 text-center"
    >
      <AlertCircle className="size-8 text-danger" aria-hidden="true" />
      <h2 className="mt-4 font-semibold">{t("errorTitle")}</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted">
        {t("errorDescription")}
      </p>
      <Button className="mt-5" variant="outline" onClick={onRetry}>
        <RefreshCw aria-hidden="true" />
        {t("retry")}
      </Button>
    </section>
  );
}
