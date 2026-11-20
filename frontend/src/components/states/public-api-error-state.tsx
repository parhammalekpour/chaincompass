"use client";

import { AlertCircle, RefreshCw } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/public-api/client";
import { getPublicApiErrorMessage } from "@/lib/public-api/error-codes";

export function PublicApiErrorState({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry: () => void;
}) {
  const locale = useLocale() === "fa" ? "fa" : "en";
  const t = useTranslations();
  const apiError = error instanceof ApiError ? error : null;
  const message = getPublicApiErrorMessage(
    apiError?.code ?? "unknown",
    apiError?.retryAfter,
    locale,
  );

  return (
    <section
      role="alert"
      className="flex flex-col items-center rounded-xl border border-border bg-card px-6 py-10 text-center"
    >
      <AlertCircle className="size-7 text-muted" aria-hidden="true" />
      <h2 className="mt-3 font-semibold">{t("states.errorTitle")}</h2>
      <p className="mt-2 max-w-md text-sm text-muted">
        {t(message.key, message.values)}
      </p>
      <Button className="mt-5" variant="outline" onClick={onRetry}>
        <RefreshCw aria-hidden="true" />
        {t("states.retry")}
      </Button>
    </section>
  );
}