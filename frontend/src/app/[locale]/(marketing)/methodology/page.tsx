import { MethodologyPage } from "@/components/marketing/methodology-page";
import { routing } from "@/i18n/routing";
import { createPageMetadata } from "@/lib/metadata";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return createPageMetadata("methodology", "/methodology", locale);
}

export default function Page() {
  return <MethodologyPage />;
}
