"use client";

import {
  Activity,
  Bell,
  Bot,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  ListFilter,
  Settings,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { Suspense } from "react";
import { usePathname } from "@/i18n/navigation";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

export const appNavigation = [
  { key: "dashboard", href: "/app", icon: LayoutDashboard },
  { key: "chains", href: "/app/chains", icon: Activity },
  { key: "chat", href: "/app/chat", icon: Bot },
  { key: "watchlist", href: "/app/watchlist", icon: ListFilter },
  { key: "alerts", href: "/app/alerts", icon: Bell },
  { key: "settings", href: "/app/settings", icon: Settings },
] as const;

export function Sidebar({
  collapsed,
  onToggle,
  onNavigate,
}: {
  collapsed: boolean;
  onToggle?: () => void;
  onNavigate?: () => void;
}) {
  return (
    <Suspense fallback={<Skeleton aria-hidden="true" className="h-full w-64" />}>
      <SidebarContent
        collapsed={collapsed}
        onToggle={onToggle}
        onNavigate={onNavigate}
      />
    </Suspense>
  );
}

function SidebarContent({
  collapsed,
  onToggle,
  onNavigate,
}: {
  collapsed: boolean;
  onToggle?: () => void;
  onNavigate?: () => void;
}) {
  const t = useTranslations("appNav");
  const pathname = usePathname();
  const CollapseIcon = collapsed ? ChevronRight : ChevronLeft;

  return (
    <TooltipProvider>
      <aside
        className={cn(
          "flex h-full flex-col border-e border-border bg-surface transition-[width] motion-safe:duration-200",
          collapsed ? "w-16" : "w-64",
        )}
      >
        <div className="flex h-16 items-center justify-between gap-2 px-3">
          {!collapsed && <span className="truncate font-semibold">{t("workspace")}</span>}
          {onToggle && (
            <Button
              variant="ghost"
              size="icon"
              aria-label={collapsed ? t("expandSidebar") : t("collapseSidebar")}
              onClick={onToggle}
            >
              <CollapseIcon aria-hidden="true" />
            </Button>
          )}
        </div>
        <Separator />
        <nav className="flex-1 space-y-1 p-2" aria-label={t("label")}>
          {appNavigation.map(({ key, href, icon: Icon }) => {
            const active =
              pathname === href ||
              (href !== "/app" && pathname.startsWith(`${href}/`));
            const link = (
              <Link
                href={href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex h-10 items-center gap-3 rounded-lg px-3 text-sm transition-colors",
                  active
                    ? "bg-primary/10 font-medium text-primary"
                    : "text-muted hover:bg-accent hover:text-foreground",
                  collapsed && "justify-center px-0",
                )}
              >
                <Icon className="size-4 shrink-0" aria-hidden="true" />
                {!collapsed && <span>{t(key)}</span>}
              </Link>
            );

            return collapsed ? (
              <Tooltip key={key}>
                <TooltipTrigger asChild>{link}</TooltipTrigger>
                <TooltipContent side="right">{t(key)}</TooltipContent>
              </Tooltip>
            ) : (
              <div key={key}>{link}</div>
            );
          })}
        </nav>
        <p className="px-3 py-4 text-center text-xs text-muted">
          {collapsed ? t("versionShort") : t("version")}
        </p>
      </aside>
    </TooltipProvider>
  );
}
