"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm, type UseFormRegisterReturn } from "react-hook-form";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { ApiError, apiRequest, getErrorMessageKey } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const schema = (email: string) =>
  z
    .object({
      currentPassword: z.string().min(1, "passwordRequired"),
      newPassword: z
        .string()
        .min(10, "passwordTooShort")
        .max(128, "passwordTooLong"),
      confirmPassword: z.string().min(1, "passwordRequired"),
    })
    .superRefine(
      ({ currentPassword, newPassword, confirmPassword }, context) => {
        if (newPassword !== confirmPassword) {
          context.addIssue({
            code: "custom",
            path: ["confirmPassword"],
            message: "passwordMismatch",
          });
        }
        if (currentPassword === newPassword) {
          context.addIssue({
            code: "custom",
            path: ["newPassword"],
            message: "passwordMustChange",
          });
        }
        if (email.trim().toLowerCase() === newPassword.toLowerCase()) {
          context.addIssue({
            code: "custom",
            path: ["newPassword"],
            message: "passwordMatchesEmail",
          });
        }
      },
    );
type Values = z.infer<ReturnType<typeof schema>>;

export function ChangePasswordForm({ email }: { email: string }) {
  const t = useTranslations("security");
  const errors = useTranslations("authErrors");
  const [success, setSuccess] = useState(false);
  const {
    register,
    handleSubmit,
    setError,
    clearErrors,
    reset,
    formState: { errors: formErrors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema(email)),
    defaultValues: { currentPassword: "", newPassword: "", confirmPassword: "" },
  });

  async function submit(values: Values) {
    clearErrors("root");
    setSuccess(false);
    try {
      await apiRequest<void>("/api/v1/auth/change-password", {
        method: "POST",
        body: {
          current_password: values.currentPassword,
          new_password: values.newPassword,
        },
      });
      reset();
      setSuccess(true);
    } catch (error) {
      if (error instanceof ApiError && error.code === "invalid_credentials") {
        setError("currentPassword", {
          type: "server",
          message: "currentPasswordInvalid",
        });
      } else {
        setError("root.server", {
          type: "server",
          message: getErrorMessageKey(error),
        });
      }
    }
  }

  const rootMessage = formErrors.root?.server?.message;

  return (
    <div className="space-y-4">
      <div aria-live="polite" aria-atomic="true">
        {success && <p role="status" className="text-sm text-muted">{t("success")}</p>}
        {rootMessage && (
          <p role="alert" className="text-sm text-destructive">
            {errors(rootMessage.replace("authErrors.", ""))}
          </p>
        )}
      </div>
      <form className="space-y-4" onSubmit={handleSubmit(submit)} noValidate>
        <PasswordField
          id="current-password"
          label={t("currentPassword")}
          autoComplete="current-password"
          error={formErrors.currentPassword?.message}
          errorText={errors(formErrors.currentPassword?.message ?? "passwordRequired")}
          registration={register("currentPassword")}
        />
        <PasswordField
          id="new-password"
          label={t("newPassword")}
          autoComplete="new-password"
          hint={t("passwordHint")}
          error={formErrors.newPassword?.message}
          errorText={errors(formErrors.newPassword?.message ?? "passwordTooShort")}
          registration={register("newPassword")}
        />
        <PasswordField
          id="confirm-new-password"
          label={t("confirmPassword")}
          autoComplete="new-password"
          error={formErrors.confirmPassword?.message}
          errorText={errors(formErrors.confirmPassword?.message ?? "passwordMismatch")}
          registration={register("confirmPassword")}
        />
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? t("submitting") : t("submit")}
        </Button>
      </form>
    </div>
  );
}

function PasswordField({
  id,
  label,
  autoComplete,
  hint,
  error,
  errorText,
  registration,
}: {
  id: string;
  label: string;
  autoComplete: "current-password" | "new-password";
  hint?: string;
  error?: string;
  errorText: string;
  registration: UseFormRegisterReturn;
}) {
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type="password"
        inputMode="text"
        autoComplete={autoComplete}
        dir="ltr"
        className="text-start"
        aria-invalid={Boolean(error)}
        aria-describedby={[hint ? hintId : "", error ? errorId : ""].filter(Boolean).join(" ") || undefined}
        {...registration}
      />
      {hint && <p id={hintId} className="text-xs text-muted">{hint}</p>}
      {error && <p id={errorId} className="text-sm text-destructive">{errorText}</p>}
    </div>
  );
}
