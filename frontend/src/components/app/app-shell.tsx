"use client";

import { useState, useSyncExternalStore } from "react";
import { Menu, Search, UserRound } from "lucide-react";
import { useTranslations } from "next-intl";
import { LanguageSwitcher } from "@/components/language-switcher";
import { SiteControls } from "@/components/site-controls";
import { Sidebar } from "@/components/app/sidebar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  getSidebarCollapsed,
  setSidebarCollapsed,
  subscribeSidebarPreference,
} from "@/lib/sidebar-preference";

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const t = useTranslations("appShell");
  const [mobileOpen, setMobileOpen] = useState(false);
  const collapsed = useSyncExternalStore(
    subscribeSidebarPreference,
    getSidebarCollapsed,
    () => false,
  );

  return (
    <div className="flex min-h-svh bg-background">
      <div className="hidden shrink-0 md:block">
        <Sidebar
          collapsed={collapsed}
          onToggle={() => setSidebarCollapsed(!collapsed)}
        />
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-border bg-background/90 px-3 backdrop-blur sm:px-5">
          <div className="flex items-center gap-2">
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  className="md:hidden"
                  aria-label={t("openNavigation")}
                >
                  <Menu aria-hidden="true" />
                </Button>
              </SheetTrigger>
              <SheetContent side="start" className="p-0">
                <SheetTitle className="sr-only">{t("navigationTitle")}</SheetTitle>
                <Sidebar
                  collapsed={false}
                  onNavigate={() => setMobileOpen(false)}
                />
              </SheetContent>
            </Sheet>
            <Button
              variant="outline"
              className="hidden gap-2 text-muted sm:inline-flex"
              aria-label={t("search")}
            >
              <Search aria-hidden="true" />
              <span>{t("search")}</span>
              <kbd dir="ltr" className="rounded border border-border px-1.5 py-0.5 text-xs">
                {t("searchShortcut")}
              </kbd>
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <LanguageSwitcher />
            <SiteControls />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="icon" aria-label={t("userMenu")}>
                  <UserRound aria-hidden="true" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>{t("guest")}</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem disabled>{t("accountSoon")}</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <main className="flex-1 p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
