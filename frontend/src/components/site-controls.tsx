"use client";

import { Moon, Sun } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Link, usePathname } from "@/i18n/navigation";
import type { AppLocale } from "@/lib/format";

export function SiteControls() {
  const t = useTranslations("common");
  const locale = useLocale() as AppLocale;
  const pathname = usePathname();
  const { resolvedTheme, setTheme } = useTheme();
  const isDark = resolvedTheme !== "light";
  const nextLocale = locale === "en" ? "fa" : "en";

  return (
    <div className="flex items-center gap-2">
      <Button
        type="button"
        variant="outline"
        size="sm"
        aria-label={isDark ? t("themeToLight") : t("themeToDark")}
        onClick={() => setTheme(isDark ? "light" : "dark")}
      >
        {isDark ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
        <span>{isDark ? t("themeToLight") : t("themeToDark")}</span>
      </Button>
      <Button asChild variant="ghost" size="sm">
        <Link href={pathname} locale={nextLocale}>
          {locale === "en" ? t("switchToPersian") : t("switchToEnglish")}
        </Link>
      </Button>
    </div>
  );
}
