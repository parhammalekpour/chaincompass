"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function PlaceholderPage({
  namespace,
  compact = false,
  values,
}: {
  namespace: string;
  compact?: boolean;
  values?: Record<string, string>;
}) {
  const t = useTranslations(namespace);
  const placeholderT = useTranslations("placeholder");

  return (
    <section className={compact ? "space-y-5" : "mx-auto max-w-6xl space-y-6"}>
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title", values)}</h1>
        <p className="text-muted">{t("description", values)}</p>
      </div>
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>
            <h2 className="text-lg font-semibold">{placeholderT("title")}</h2>
          </CardTitle>
          <CardDescription>{placeholderT("description")}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild variant="outline">
            <Link href="/app">{placeholderT("backToDashboard")}</Link>
          </Button>
        </CardContent>
      </Card>
    </section>
  );
}
