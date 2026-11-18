"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/auth-provider";
import { PageSkeleton } from "@/components/states/page-skeleton";

export function AppAuthGuard({
  children,
  locale,
}: {
  children: React.ReactNode;
  locale: string;
}) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status !== "anonymous") return;
    const next = `${window.location.pathname}${window.location.search}`;
    router.replace(`/${locale}/login?next=${encodeURIComponent(next)}`);
  }, [locale, router, status]);

  if (status !== "authenticated") return <PageSkeleton />;
  return children;
}
