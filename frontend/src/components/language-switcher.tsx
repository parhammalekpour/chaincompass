"use client";

import { useLocale, useTranslations } from "next-intl";
import { Suspense } from "react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { usePathname } from "@/i18n/navigation";
import { changeLocale } from "@/lib/locale-navigation";

export function LanguageSwitcher() {
  return (
    <Suspense fallback={<Skeleton aria-hidden="true" className="h-9 w-28" />}>
      <LanguageSwitcherContent />
    </Suspense>
  );
}

function LanguageSwitcherContent() {
  const locale = useLocale() as "en" | "fa";
  const t = useTranslations("common");
  const pathname = usePathname();
  const [isPending, setIsPending] = useState(false);

  function switchLocale(nextLocale: "en" | "fa") {
    setIsPending(true);
    changeLocale(pathname, window.location.search, nextLocale);
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          aria-label={t("languageLabel")}
          aria-busy={isPending}
        >
          English | فارسی
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          aria-current={locale === "en" ? "true" : undefined}
          onSelect={() => switchLocale("en")}
        >
          English
        </DropdownMenuItem>
        <DropdownMenuItem
          aria-current={locale === "fa" ? "true" : undefined}
          onSelect={() => switchLocale("fa")}
        >
          فارسی
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
