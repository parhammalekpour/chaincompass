"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { useRouter } from "@/i18n/navigation";
import { ApiError, apiRequest, getErrorMessageKey } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Link } from "@/i18n/navigation";

const schema = z
  .object({
    password: z.string().min(10, "passwordTooShort").max(128, "passwordTooLong"),
    confirmPassword: z.string().min(1, "passwordRequired"),
  })
  .refine((value) => value.password === value.confirmPassword, {
    path: ["confirmPassword"],
    message: "passwordMismatch",
  });
type Values = z.infer<typeof schema>;
type TokenState = "loading" | "ready" | "missing" | "invalid" | "success";

export function ResetPasswordForm() {
  const router = useRouter();
  const t = useTranslations("resetPassword");
  const errors = useTranslations("authErrors");
  const [tokenState, setTokenState] = useState<TokenState>("loading");
  const [token, setToken] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const started = useRef(false);
  const {
    register,
    handleSubmit,
    setError,
    clearErrors,
    formState: { errors: formErrors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { password: "", confirmPassword: "" },
  });

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const currentUrl = new URL(window.location.href);
    const token = currentUrl.searchParams.get("token");
    window.history.replaceState(null, "", currentUrl.pathname);
    if (!token) {
      queueMicrotask(() => setTokenState("missing"));
      return;
    }
    queueMicrotask(() => {
      setToken(token);
      setTokenState("ready");
    });
  }, []);

  async function submit(values: Values) {
    if (!token) {
      setTokenState("missing");
      return;
    }
    clearErrors("root");
    try {
      await apiRequest("/api/v1/auth/reset-password", {
        method: "POST",
        body: { token, new_password: values.password },
        authRetry: false,
      });
      setToken(null);
      setTokenState("success");
      router.replace("/login?notice=password_reset");
    } catch (error) {
      if (error instanceof ApiError && error.code === "invalid_reset_token") {
        setTokenState("invalid");
      } else {
        setError("root.server", {
          type: "server",
          message: getErrorMessageKey(error),
        });
      }
    }
  }

  if (tokenState === "loading") {
    return <p role="status" className="text-sm text-muted">{t("loading")}</p>;
  }
  if (tokenState === "missing" || tokenState === "invalid") {
    return (
      <div aria-live="polite" className="space-y-4 text-start">
        <h1 className="text-2xl font-semibold">{t("invalidTitle")}</h1>
        <p role="alert" className="text-sm text-destructive">
          {errors("invalidResetToken")}
        </p>
        <Link href="/forgot-password" className="text-sm text-primary underline-offset-4 hover:underline">
          {t("requestAnother")}
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 text-start">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-sm text-muted">{t("passwordHint")}</p>
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
          <Label htmlFor="reset-password">{t("newPassword")}</Label>
          <Input
            id="reset-password"
            type={showPassword ? "text" : "password"}
            inputMode="text"
            autoComplete="new-password"
            dir="ltr"
            className="text-start"
            aria-invalid={Boolean(formErrors.password)}
            aria-describedby={formErrors.password ? "reset-password-error" : "reset-password-hint"}
            {...register("password")}
          />
          <p id="reset-password-hint" className="text-xs text-muted">{t("passwordHint")}</p>
          {formErrors.password && (
            <p id="reset-password-error" className="text-sm text-destructive">
              {errors(formErrors.password.message ?? "passwordTooShort")}
            </p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="reset-confirm">{t("confirmPassword")}</Label>
          <Input
            id="reset-confirm"
            type={showPassword ? "text" : "password"}
            inputMode="text"
            autoComplete="new-password"
            dir="ltr"
            className="text-start"
            aria-invalid={Boolean(formErrors.confirmPassword)}
            aria-describedby={formErrors.confirmPassword ? "reset-confirm-error" : undefined}
            {...register("confirmPassword")}
          />
          {formErrors.confirmPassword && (
            <p id="reset-confirm-error" className="text-sm text-destructive">
              {errors(formErrors.confirmPassword.message ?? "passwordMismatch")}
            </p>
          )}
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={() => setShowPassword((value) => !value)}
        >
          {showPassword ? t("hidePassword") : t("showPassword")}
        </Button>
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? t("submitting") : t("submit")}
        </Button>
      </form>
    </div>
  );
}
