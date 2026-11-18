"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

export function GoogleSignIn() {
  const t = useTranslations("authErrors");
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function beginSignIn() {
    setPending(true);
    setMessage(null);
    try {
      const response = await fetch("/api/v1/auth/google/login", {
        credentials: "same-origin",
        redirect: "manual",
      });
      if (response.status === 501) {
        setMessage("googleComingSoon");
        return;
      }
      window.location.assign(
        new URL("/api/v1/auth/google/login", window.location.origin).toString(),
      );
    } catch {
      setMessage("network");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-2">
      <Button
        type="button"
        variant="outline"
        className="w-full"
        disabled={pending}
        onClick={() => void beginSignIn()}
      >
        {t("googleButton")}
      </Button>
      {message && (
        <p role="status" className="text-sm text-muted">
          {t(message)}
        </p>
      )}
    </div>
  );
}
