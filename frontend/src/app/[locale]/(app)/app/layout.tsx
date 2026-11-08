import { AppShell } from "@/components/app/app-shell";
import { setRequestLocale } from "next-intl/server";

export default async function AppLayout({
  children,
  params,
}: Readonly<{ children: React.ReactNode; params: Promise<{ locale: string }> }>) {
  const { locale } = await params;
  setRequestLocale(locale);
  // TODO: Enforce authentication and authorization when auth is implemented.
  return <AppShell>{children}</AppShell>;
}
