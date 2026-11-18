"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { apiRequest } from "@/lib/api/client";
import { useAuth } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Link } from "@/i18n/navigation";

type State = "verifying" | "success" | "invalid";

export function VerifyEmailPage() {
  const t = useTranslations("verifyEmail");
  const errors = useTranslations("authErrors");
  const { status, user, refreshCurrentUser } = useAuth();
  const [state, setState] = useState<State>("verifying");
  const [resendState, setResendState] = useState<"idle" | "sent" | "error">("idle");
  const [retrySeconds, setRetrySeconds] = useState(0);
  const [resending, setResending] = useState(false);
  const started = useRef(false);
  const refreshed = useRef(false);
  const emailRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const currentUrl = new URL(window.location.href);
    const token = currentUrl.searchParams.get("token");
    window.history.replaceState(null, "", currentUrl.pathname);
    if (!token) {
      queueMicrotask(() => setState("invalid"));
      return;
    }
    void apiRequest("/api/v1/auth/verify-email", {
      method: "POST",
      body: { token },
      authRetry: false,
    })
      .then(() => setState("success"))
      .catch(() => setState("invalid"));
  }, []);

  useEffect(() => {
    if (state !== "success" || status !== "authenticated" || refreshed.current) return;
    refreshed.current = true;
    void refreshCurrentUser().catch(() => undefined);
  }, [refreshCurrentUser, state, status]);

  useEffect(() => {
    if (retrySeconds <= 0) return;
    const timer = window.setTimeout(
      () => setRetrySeconds((seconds) => Math.max(0, seconds - 1)),
      1000,
    );
    return () => window.clearTimeout(timer);
  }, [retrySeconds]);

  async function resend() {
    const email = user?.email ?? emailRef.current?.value.trim();
    if (!email || resending || retrySeconds > 0) return;
    setResendState("idle");
    setResending(true);
    try {
      await apiRequest("/api/v1/auth/resend-verification", {
        method: "POST",
        body: { email },
        authRetry: false,
      });
      setResendState("sent");
      setRetrySeconds(60);
    } catch (error) {
      setResendState("error");
      if (
        typeof error === "object" &&
        error !== null &&
        "retryAfterSeconds" in error &&
        typeof error.retryAfterSeconds === "number"
      ) {
        setRetrySeconds(Math.max(60, error.retryAfterSeconds));
      }
    } finally {
      setResending(false);
    }
  }

  if (state === "verifying") {
    return <p role="status" className="text-sm text-muted">{t("verifying")}</p>;
  }
  if (state === "success") {
    return (
      <div aria-live="polite" className="space-y-4 text-start">
        <h1 className="text-2xl font-semibold">{t("successTitle")}</h1>
        <p role="status" className="text-sm text-muted">{t("successMessage")}</p>
        {status === "authenticated" ? (
          <Link href="/app" className="text-sm text-primary underline-offset-4 hover:underline">
            {t("continueToApp")}
          </Link>
        ) : (
          <Link href="/login" className="text-sm text-primary underline-offset-4 hover:underline">
            {t("login")}
          </Link>
        )}
      </div>
    );
  }

  return (
    <div aria-live="polite" className="space-y-4 text-start">
      <h1 className="text-2xl font-semibold">{t("invalidTitle")}</h1>
      <p role="alert" className="text-sm text-destructive">{errors("invalidEmailToken")}</p>
      {status !== "authenticated" && (
        <div className="space-y-2">
          <Label htmlFor="verify-email">{t("email")}</Label>
          <Input
            id="verify-email"
            type="email"
            inputMode="email"
            autoComplete="email"
            autoCapitalize="none"
            dir="ltr"
            className="text-start"
            ref={emailRef}
          />
        </div>
      )}
      {resendState === "sent" && <p role="status" className="text-sm text-muted">{t("resendSuccess")}</p>}
      {resendState === "error" && (
        <p role="alert" className="text-sm text-destructive">
          {retrySeconds > 0
            ? errors("rateLimited", { seconds: String(retrySeconds) })
            : errors("generic")}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" variant="outline" disabled={resending || retrySeconds > 0} onClick={() => void resend()}>
          {resending
            ? t("resendPending")
            : retrySeconds > 0
              ? t("resendCountdown", { seconds: String(retrySeconds) })
              : t("resend")}
        </Button>
        {status !== "authenticated" && (
          <Link href="/login" className="text-sm text-primary underline-offset-4 hover:underline">
            {t("login")}
          </Link>
        )}
      </div>
    </div>
  );
}
