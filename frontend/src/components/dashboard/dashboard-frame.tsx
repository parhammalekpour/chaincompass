"use client";

import type { ReactNode } from "react";
import type { AppLocale } from "@/lib/format";

export function DashboardFrame({
  locale,
  children,
}: {
  locale: AppLocale;
  children: ReactNode;
}) {
  return (
    <section
      dir={locale === "fa" ? "rtl" : "ltr"}
      className="mx-auto max-w-7xl space-y-6 text-start"
    >
      {children}
    </section>
  );
}