"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useAuth } from "@/components/auth/auth-provider";
import { useRouter } from "@/i18n/navigation";

export function GoogleCallback({ locale }: { locale: "en" | "fa" }) {
  const t = useTranslations("authCallback");
  const router = useRouter();
  const { restoreSession } = useAuth();
  const started = useRef(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void restoreSession()
      .then(() => router.replace("/app"))
      .catch(() => {
        setFailed(true);
        router.replace("/login?error=oauth_failed");
      });
  }, [restoreSession, router, locale]);

  return (
    <p role={failed ? "alert" : "status"} className="text-sm text-muted">
      {failed ? t("failed") : t("loading")}
    </p>
  );
}
