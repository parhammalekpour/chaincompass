import { MarketingHeader } from "@/components/marketing/header";
import { SiteFooter } from "@/components/site-footer";
import { PublicQueryProvider } from "@/components/providers/public-query-provider";
import { setRequestLocale } from "next-intl/server";

export default async function MarketingLayout({
  children,
  params,
}: Readonly<{ children: React.ReactNode; params: Promise<{ locale: string }> }>) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <div className="min-h-svh">
      <PublicQueryProvider>
        <MarketingHeader />
        {children}
        <SiteFooter />
      </PublicQueryProvider>
    </div>
  );
}
