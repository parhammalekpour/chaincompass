"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { useAuth } from "@/components/auth/auth-provider";
import { GoogleSignIn } from "@/components/auth/google-sign-in";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Link } from "@/i18n/navigation";
import { ApiError, getErrorMessageKey } from "@/lib/api/client";
import { sanitizeNextPath } from "@/lib/safe-next";
import { PageSkeleton } from "@/components/states/page-skeleton";

const loginSchema = z.object({
  email: z.email({ error: "emailInvalid" }),
  password: z.string().min(1, "passwordRequired").max(128, "passwordTooLong"),
});
type LoginValues = z.infer<typeof loginSchema>;

export function LoginForm({ locale }: { locale: "en" | "fa" }) {
  const t = useTranslations("login");
  const errors = useTranslations("authErrors");
  const { status, login } = useAuth();
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const [retrySeconds, setRetrySeconds] = useState(0);
  const {
    register,
    handleSubmit,
    setError,
    clearErrors,
    formState: { errors: formErrors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  useEffect(() => {
    if (status !== "authenticated") return;
    const next = new URLSearchParams(window.location.search).get("next");
    router.replace(sanitizeNextPath(next, locale));
  }, [locale, router, status]);

  useEffect(() => {
    if (retrySeconds <= 0) return;
    const timer = window.setTimeout(
      () => setRetrySeconds((seconds) => Math.max(0, seconds - 1)),
      1000,
    );
    return () => window.clearTimeout(timer);
  }, [retrySeconds]);

  async function submit(values: LoginValues) {
    clearErrors("root");
    setRetrySeconds(0);
    try {
      await login(values.email.trim(), values.password);
    } catch (error) {
      setError("root.server", {
        type: "server",
        message: getErrorMessageKey(error),
      });
      if (error instanceof ApiError && error.code === "rate_limited") {
        setRetrySeconds(error.retryAfterSeconds ?? 0);
      }
    }
  }

  const rootMessage = formErrors.root?.server?.message;
  if (status === "loading") return <PageSkeleton />;

  return (
    <div className="space-y-6">
      <div className="space-y-2 text-start">
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-sm text-muted">{t("description")}</p>
      </div>

      <div
        aria-live="polite"
        aria-atomic="true"
        className="min-h-0"
      >
        {rootMessage && (
          <p role="alert" className="rounded-lg border border-destructive/40 p-3 text-sm text-destructive">
            {rootMessage === "authErrors.rateLimited"
              ? errors("rateLimited", { seconds: retrySeconds })
              : errors(rootMessage.replace("authErrors.", ""))}
          </p>
        )}
      </div>

      <form className="space-y-4" onSubmit={handleSubmit(submit)} noValidate>
        <div className="space-y-2">
          <Label htmlFor="login-email">{t("email")}</Label>
          <Input
            id="login-email"
            type="email"
            inputMode="email"
            autoComplete="email"
            autoCapitalize="none"
            spellCheck={false}
            dir="ltr"
            className="text-start"
            aria-invalid={Boolean(formErrors.email)}
            aria-describedby={formErrors.email ? "login-email-error" : undefined}
            {...register("email")}
          />
          {formErrors.email && (
            <p id="login-email-error" className="text-sm text-destructive">
              {errors(formErrors.email.message ?? "emailInvalid")}
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="login-password">{t("password")}</Label>
          <div className="flex gap-2">
            <Input
              id="login-password"
              type={showPassword ? "text" : "password"}
              inputMode="text"
              autoComplete="current-password"
              dir="ltr"
              className="text-start"
              aria-invalid={Boolean(formErrors.password)}
              aria-describedby={
                formErrors.password ? "login-password-error" : undefined
              }
              {...register("password")}
            />
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowPassword((value) => !value)}
              aria-label={showPassword ? t("hidePassword") : t("showPassword")}
            >
              {showPassword ? t("hidePassword") : t("showPassword")}
            </Button>
          </div>
          {formErrors.password && (
            <p id="login-password-error" className="text-sm text-destructive">
              {errors(formErrors.password.message ?? "passwordRequired")}
            </p>
          )}
        </div>

        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? t("submitting") : t("submit")}
        </Button>
      </form>

      <GoogleSignIn />
      <p className="text-center text-sm text-muted">
        {t("noAccount")}{" "}
        <Link href="/register" className="font-medium text-primary underline-offset-4 hover:underline">
          {t("registerLink")}
        </Link>
      </p>
    </div>
  );
}
