"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { ApiError, apiRequest } from "@/lib/api/client";
import { Button } from "@/components/ui/button";

export function ResendVerificationButton({ email }: { email: string }) {
  const t = useTranslations("appShell");
  const errors = useTranslations("authErrors");
  const [retrySeconds, setRetrySeconds] = useState(0);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<"sent" | "error" | null>(null);

  useEffect(() => {
    if (retrySeconds <= 0) return;
    const timer = window.setTimeout(
      () => setRetrySeconds((seconds) => Math.max(0, seconds - 1)),
      1000,
    );
    return () => window.clearTimeout(timer);
  }, [retrySeconds]);

  async function resend() {
    if (pending || retrySeconds > 0) return;
    setMessage(null);
    setPending(true);
    try {
      await apiRequest("/api/v1/auth/resend-verification", {
        method: "POST",
        body: { email },
        authRetry: false,
      });
      setMessage("sent");
      setRetrySeconds(60);
    } catch (error) {
      setMessage("error");
      if (error instanceof ApiError && error.code === "rate_limited") {
        setRetrySeconds(Math.max(60, error.retryAfterSeconds ?? 60));
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button
        variant="outline"
        size="sm"
        disabled={pending || retrySeconds > 0}
        onClick={() => void resend()}
      >
        {pending
          ? t("resendPending")
          : retrySeconds > 0
            ? t("resendCountdown", { seconds: String(retrySeconds) })
            : t("resendVerification")}
      </Button>
      {message === "sent" && <span role="status" className="text-xs text-muted">{t("resendConfirmation")}</span>}
      {message === "error" && (
        <span role="alert" className="text-xs text-destructive">
          {retrySeconds > 0
            ? errors("rateLimited", { seconds: String(retrySeconds) })
            : errors("generic")}
        </span>
      )}
    </div>
  );
}
