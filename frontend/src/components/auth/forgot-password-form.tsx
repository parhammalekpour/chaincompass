"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { ApiError, apiRequest, getErrorMessageKey } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Link } from "@/i18n/navigation";

const schema = z.object({
  email: z.email({ error: "emailInvalid" }),
});
type Values = z.infer<typeof schema>;

export function ForgotPasswordForm() {
  const t = useTranslations("forgotPassword");
  const errors = useTranslations("authErrors");
  const [submitted, setSubmitted] = useState(false);
  const [retrySeconds, setRetrySeconds] = useState(0);
  const {
    register,
    handleSubmit,
    setError,
    clearErrors,
    formState: { errors: formErrors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { email: "" },
  });

  useEffect(() => {
    if (retrySeconds <= 0) return;
    const timer = window.setTimeout(
      () => setRetrySeconds((seconds) => Math.max(0, seconds - 1)),
      1000,
    );
    return () => window.clearTimeout(timer);
  }, [retrySeconds]);

  async function submit(values: Values) {
    clearErrors("root");
    try {
      await apiRequest("/api/v1/auth/forgot-password", {
        method: "POST",
        body: { email: values.email.trim() },
        authRetry: false,
      });
    } catch (error) {
      if (error instanceof ApiError && error.code === "rate_limited") {
        setRetrySeconds(error.retryAfterSeconds ?? 0);
      } else {
        setError("root.server", {
          type: "server",
          message: getErrorMessageKey(error),
        });
      }
    } finally {
      setSubmitted(true);
    }
  }

  if (submitted) {
    return (
      <div aria-live="polite" className="space-y-4 text-start">
        <h1 className="text-2xl font-semibold">{t("successTitle")}</h1>
        <p role="status" className="text-sm text-muted">{t("successMessage")}</p>
        {retrySeconds > 0 && (
          <p className="text-sm text-muted">
            {errors("rateLimited", { seconds: String(retrySeconds) })}
          </p>
        )}
        <Link href="/login" className="text-sm text-primary underline-offset-4 hover:underline">
          {t("backToLogin")}
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 text-start">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-sm text-muted">{t("description")}</p>
      </div>
      <div aria-live="polite" aria-atomic="true">
        {formErrors.root?.server && (
          <p role="alert" className="rounded-lg border border-destructive/40 p-3 text-sm text-destructive">
            {errors(formErrors.root.server.message?.replace("authErrors.", "") ?? "generic")}
          </p>
        )}
      </div>
      <form className="space-y-4" onSubmit={handleSubmit(submit)} noValidate>
        <div className="space-y-2">
          <Label htmlFor="forgot-email">{t("email")}</Label>
          <Input
            id="forgot-email"
            type="email"
            inputMode="email"
            autoComplete="email"
            autoCapitalize="none"
            spellCheck={false}
            dir="ltr"
            className="text-start"
            aria-invalid={Boolean(formErrors.email)}
            aria-describedby={formErrors.email ? "forgot-email-error" : undefined}
            {...register("email")}
          />
          {formErrors.email && (
            <p id="forgot-email-error" className="text-sm text-destructive">
              {errors(formErrors.email.message ?? "emailInvalid")}
            </p>
          )}
        </div>
        <Button type="submit" className="w-full" disabled={isSubmitting || retrySeconds > 0}>
          {isSubmitting ? t("submitting") : retrySeconds > 0
            ? errors("rateLimited", { seconds: String(retrySeconds) })
            : t("submit")}
        </Button>
      </form>
      <Link href="/login" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("backToLogin")}
      </Link>
    </div>
  );
}
