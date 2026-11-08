 "use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import { createPageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return createPageMetadata("notFound", "/not-found", locale);
}

export default function LocaleNotFound() {
  const t = useTranslations("states");

  return (
    <main className="mx-auto flex min-h-[60svh] max-w-3xl flex-col items-center justify-center gap-4 px-6 text-center">
      <h1 className="text-3xl font-semibold">{t("notFoundTitle")}</h1>
      <p className="text-muted">{t("notFoundDescription")}</p>
      <Button asChild>
        <Link href="/">{t("backHome")}</Link>
      </Button>
    </main>
  );
}
