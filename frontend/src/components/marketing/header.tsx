"use client";

import { Compass, Menu } from "lucide-react";
import { useTranslations } from "next-intl";
import { LanguageSwitcher } from "@/components/language-switcher";
import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

export function MarketingHeader() {
  const t = useTranslations("marketing");
  const common = useTranslations("common");

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" className="inline-flex items-center gap-2 font-semibold">
          <Compass className="size-5 text-primary" aria-hidden="true" />
          {common("appName")}
        </Link>

        <nav className="hidden items-center gap-6 md:flex" aria-label={t("navLabel")}>
          <Link className="text-sm text-muted hover:text-foreground" href="/methodology">
            {t("methodology")}
          </Link>
          <span aria-disabled="true" className="inline-flex items-center gap-2 text-sm text-muted">
            {t("learn")}
            <span className="rounded-full border border-border px-2 py-0.5 text-xs">
              {t("soon")}
            </span>
          </span>
          <Link className="text-sm text-muted hover:text-foreground" href="/login">
            {t("login")}
          </Link>
          <Button asChild size="sm">
            <Link href="/register">{t("getStarted")}</Link>
          </Button>
          <LanguageSwitcher />
        </nav>

        <div className="flex items-center gap-2 md:hidden">
          <LanguageSwitcher />
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="outline" size="icon" aria-label={t("openMenu")}>
                <Menu aria-hidden="true" />
              </Button>
            </SheetTrigger>
            <SheetContent side="end">
              <SheetHeader>
                <SheetTitle>{t("menuTitle")}</SheetTitle>
              </SheetHeader>
              <nav className="flex flex-col gap-5 px-4" aria-label={t("navLabel")}>
                <Link href="/methodology">{t("methodology")}</Link>
                <span className="inline-flex items-center gap-2 text-muted">
                  {t("learn")}
                  <span className="rounded-full border border-border px-2 py-0.5 text-xs">
                    {t("soon")}
                  </span>
                </span>
                <Link href="/login">{t("login")}</Link>
                <Button asChild>
                  <Link href="/register">{t("getStarted")}</Link>
                </Button>
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
