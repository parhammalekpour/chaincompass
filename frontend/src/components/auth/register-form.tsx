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
import { getErrorMessageKey } from "@/lib/api/client";
import { sanitizeNextPath } from "@/lib/safe-next";
import { PageSkeleton } from "@/components/states/page-skeleton";

const registerSchema = z
  .object({
    email: z.email({ error: "emailInvalid" }),
    password: z
      .string()
      .min(10, "passwordTooShort")
      .max(128, "passwordTooLong"),
    locale: z.enum(["en", "fa"]),
  })
  .superRefine(({ email, password }, context) => {
    if (email.trim().toLowerCase() === password.toLowerCase()) {
      context.addIssue({
        code: "custom",
        path: ["password"],
        message: "passwordMatchesEmail",
      });
    }
  });
type RegisterValues = z.infer<typeof registerSchema>;

export function RegisterForm({ locale }: { locale: "en" | "fa" }) {
  const t = useTranslations("register");
  const errors = useTranslations("authErrors");
  const { status, register: createAccount } = useAuth();
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const [registered, setRegistered] = useState(false);
  const {
    register,
    handleSubmit,
    setError,
    clearErrors,
    formState: { errors: formErrors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { email: "", password: "", locale },
  });

  useEffect(() => {
    if (status !== "authenticated") return;
    const next = new URLSearchParams(window.location.search).get("next");
    router.replace(sanitizeNextPath(next, locale));
  }, [locale, router, status]);

  async function submit(values: RegisterValues) {
    clearErrors("root");
    try {
      await createAccount(values.email.trim(), values.password, values.locale);
      setRegistered(true);
    } catch (error) {
      setError("root.server", {
        type: "server",
        message: getErrorMessageKey(error),
      });
    }
  }

  const rootMessage = formErrors.root?.server?.message;
  if (status === "loading") return <PageSkeleton />;
  if (registered) {
    return (
      <div aria-live="polite" className="space-y-4 text-start">
        <h1 className="text-2xl font-semibold">{t("successTitle")}</h1>
        <p role="status" className="text-sm text-muted">
          {t("successMessage")}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2 text-start">
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-sm text-muted">{t("description")}</p>
      </div>

      <div aria-live="polite" aria-atomic="true">
        {rootMessage && (
          <p role="alert" className="rounded-lg border border-destructive/40 p-3 text-sm text-destructive">
            {errors(rootMessage.replace("authErrors.", ""))}
          </p>
        )}
      </div>

      <form className="space-y-4" onSubmit={handleSubmit(submit)} noValidate>
        <div className="space-y-2">
          <Label htmlFor="register-email">{t("email")}</Label>
          <Input
            id="register-email"
            type="email"
            inputMode="email"
            autoComplete="email"
            autoCapitalize="none"
            spellCheck={false}
            dir="ltr"
            className="text-start"
            aria-invalid={Boolean(formErrors.email)}
            aria-describedby={
              formErrors.email ? "register-email-error" : undefined
            }
            {...register("email")}
          />
          {formErrors.email && (
            <p id="register-email-error" className="text-sm text-destructive">
              {errors(formErrors.email.message ?? "emailInvalid")}
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="register-password">{t("password")}</Label>
          <div className="flex gap-2">
            <Input
              id="register-password"
              type={showPassword ? "text" : "password"}
              inputMode="text"
              autoComplete="new-password"
              dir="ltr"
              className="text-start"
              aria-invalid={Boolean(formErrors.password)}
              aria-describedby={[
                "register-password-hint",
                formErrors.password ? "register-password-error" : "",
              ]
                .filter(Boolean)
                .join(" ")}
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
          <p id="register-password-hint" className="text-xs text-muted">
            {t("passwordLengthHint")}
          </p>
          {formErrors.password && (
            <p id="register-password-error" className="text-sm text-destructive">
              {errors(formErrors.password.message ?? "passwordTooShort")}
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="register-locale">{t("language")}</Label>
          <select
            id="register-locale"
            className="h-9 w-full rounded-lg border border-input bg-background px-3 text-start"
            {...register("locale")}
          >
            <option value="en">{t("english")}</option>
            <option value="fa">{t("persian")}</option>
          </select>
        </div>

        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? t("submitting") : t("submit")}
        </Button>
      </form>

      <GoogleSignIn />
      <p className="text-center text-sm text-muted">
        {t("haveAccount")}{" "}
        <Link href="/login" className="font-medium text-primary underline-offset-4 hover:underline">
          {t("loginLink")}
        </Link>
      </p>
    </div>
  );
}
