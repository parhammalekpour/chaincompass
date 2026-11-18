"use client";

import { useTranslations } from "next-intl";
import { useAuth } from "@/components/auth/auth-provider";
import { ChangePasswordForm } from "@/components/auth/change-password-form";

export function SecuritySettings() {
  const t = useTranslations("security");
  const { user } = useAuth();

  return (
    <div className="mx-auto max-w-2xl space-y-6 text-start">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-sm text-muted">{t("description")}</p>
      </header>
      <section className="space-y-4 rounded-xl border border-border bg-surface p-5">
        <h2 className="text-lg font-semibold">{t("account")}</h2>
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div className="space-y-1">
            <dt className="text-muted">{t("email")}</dt>
            <dd dir="ltr" className="text-start">{user?.email}</dd>
          </div>
          <div className="space-y-1">
            <dt className="text-muted">{t("verificationStatus")}</dt>
            <dd>{user?.email_verified ? t("verified") : t("notVerified")}</dd>
          </div>
        </dl>
      </section>
      <section className="space-y-4 rounded-xl border border-border bg-surface p-5">
        <h2 className="text-lg font-semibold">{t("changePassword")}</h2>
        <ChangePasswordForm email={user?.email ?? ""} />
      </section>
    </div>
  );
}
