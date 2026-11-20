"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useAuth } from "@/components/auth/auth-provider";
import { PageSkeleton } from "@/components/states/page-skeleton";
import { Button } from "@/components/ui/button";

export function AppAuthGuard({
  children,
  locale,
}: {
  children: React.ReactNode;
  locale: string;
}) {
  const { status, retryInitialSession } = useAuth();
  const router = useRouter();
  const t = useTranslations();

  useEffect(() => {
    if (status !== "anonymous") return;
    const next = `${window.location.pathname}${window.location.search}`;
    router.replace(`/${locale}/login?next=${encodeURIComponent(next)}`);
  }, [locale, router, status]);

  if (status === "error") {
    return (
      <section
        role="alert"
        className="mx-auto flex max-w-lg flex-col items-center rounded-xl border border-border bg-card px-6 py-10 text-center"
      >
        <AlertCircle className="size-7 text-muted" aria-hidden="true" />
        <h1 className="mt-3 font-semibold">{t("auth.refreshError")}</h1>
        <Button
          className="mt-5"
          variant="outline"
          onClick={() => void retryInitialSession()}
        >
          <RefreshCw aria-hidden="true" />
          {t("states.retry")}
        </Button>
      </section>
    );
  }

  if (status !== "authenticated") return <PageSkeleton />;
  return children;
}
