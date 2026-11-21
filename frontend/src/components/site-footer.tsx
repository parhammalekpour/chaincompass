"use client";

import { Compass } from "lucide-react";
import { useTranslations } from "next-intl";
import { LanguageSwitcher } from "@/components/language-switcher";
import { Link } from "@/i18n/navigation";

type SiteFooterProps = {
  variant?: "full" | "compact";
};

const SOURCES = [
  { key: "binance", href: "https://www.binance.com/" },
  { key: "defillama", href: "https://defillama.com/" },
  { key: "coinMetrics", href: "https://coinmetrics.io/" },
  { key: "coingecko", href: "https://www.coingecko.com/" },
  { key: "mempool", href: "https://mempool.space/" },
  { key: "blockchain", href: "https://www.blockchain.com/" },
] as const;

export function SiteFooter({ variant = "full" }: SiteFooterProps) {
  const t = useTranslations("siteFooter");
  const common = useTranslations("common");
  const compact = variant === "compact";

  return (
    <footer className="border-t border-border bg-surface/50">
      <div
        className={
          compact
            ? "mx-auto flex max-w-7xl flex-col gap-3 px-4 py-5 text-xs text-muted sm:px-6"
            : "mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-[1fr_auto_auto] md:items-start"
        }
      >
        <div className="space-y-3">
          {!compact && (
            <Link href="/" className="inline-flex items-center gap-2 font-semibold">
              <Compass className="size-5 text-primary" aria-hidden="true" />
              {common("appName")}
            </Link>
          )}
          <p className={compact ? "max-w-3xl leading-5" : "max-w-md text-sm leading-6 text-muted"}>
            {t("disclaimer")}
          </p>
        </div>
        <nav
          className="flex flex-wrap gap-x-5 gap-y-2 text-sm"
          aria-label={t("productLinks")}
        >
          <Link className="text-muted hover:text-foreground" href="/methodology">
            {t("methodology")}
          </Link>
          <Link className="text-muted hover:text-foreground" href="/legal">
            {t("legal")}
          </Link>
          {!compact && (
            <Link className="text-muted hover:text-foreground" href="/learn">
              {t("learn")}
            </Link>
          )}
        </nav>
        <div className="flex flex-col items-start gap-3 text-sm">
          {!compact && <h2 className="font-medium">{t("sources")}</h2>}
          <ul
            className={
              compact
                ? "flex flex-wrap gap-x-4 gap-y-1"
                : "flex flex-col gap-2"
            }
          >
            {SOURCES.map((source) => {
              const name = t(`sourceNames.${source.key}`);
              return (
                <li key={source.key}>
                  <a
                    href={source.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={t("visitSource", { source: name })}
                    className="text-muted underline-offset-4 hover:text-foreground hover:underline"
                  >
                    {name}
                  </a>
                </li>
              );
            })}
          </ul>
          {!compact && <LanguageSwitcher />}
        </div>
      </div>
    </footer>
  );
}
