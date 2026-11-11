import { Compass } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { LanguageSwitcher } from "@/components/language-switcher";
import { Link } from "@/i18n/navigation";

export async function MarketingFooter({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "marketing" });
  const common = await getTranslations({ locale, namespace: "common" });

  return (
    <footer className="border-t border-border bg-surface/50">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-[1fr_auto_auto] md:items-start">
        <div className="space-y-3">
          <Link href="/" className="inline-flex items-center gap-2 font-semibold">
            <Compass className="size-5 text-primary" aria-hidden="true" />
            {common("appName")}
          </Link>
          <p className="max-w-md text-sm leading-6 text-muted">
            {t("footerDisclaimer")}
          </p>
        </div>
        <nav className="flex flex-col gap-3 text-sm" aria-label={t("productLinks")}>
          <span className="font-medium">{t("productLinks")}</span>
          <Link className="text-muted hover:text-foreground" href="/methodology">
            {t("methodology")}
          </Link>
          <Link className="text-muted hover:text-foreground" href="/learn">
            {t("learn")}
          </Link>
        </nav>
        <div className="flex flex-col items-start gap-3 text-sm">
          <Link className="text-muted hover:text-foreground" href="/legal">
            {t("legal")}
          </Link>
          <LanguageSwitcher />
        </div>
      </div>
    </footer>
  );
}
