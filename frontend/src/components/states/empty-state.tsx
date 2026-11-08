"use client";

import type { LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}) {
  const t = useTranslations("states");

  return (
    <section
      className="flex flex-col items-center rounded-xl border border-dashed border-border px-6 py-12 text-center"
      aria-labelledby="empty-state-title"
    >
      <Icon className="size-8 text-muted" aria-hidden="true" />
      <h2 id="empty-state-title" className="mt-4 font-semibold">
        {title || t("emptyTitle")}
      </h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted">
        {description || t("emptyDescription")}
      </p>
      {action && (
        <Button className="mt-5" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </section>
  );
}
