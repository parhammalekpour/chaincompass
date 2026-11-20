import { AppShell } from "@/components/app/app-shell";
import { AppAuthGuard } from "@/components/auth/app-auth-guard";
import { PublicQueryProvider } from "@/components/providers/public-query-provider";
import { setRequestLocale } from "next-intl/server";

export default async function AppLayout({
  children,
  params,
}: Readonly<{ children: React.ReactNode; params: Promise<{ locale: string }> }>) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <PublicQueryProvider>
      <AppAuthGuard locale={locale}>
        <AppShell>{children}</AppShell>
      </AppAuthGuard>
    </PublicQueryProvider>
  );
}
