import { PlaceholderPage } from "@/components/placeholder-page";
import { createPageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return createPageMetadata("alerts", "/app/alerts", locale);
}

export default function Page() {
  return <PlaceholderPage namespace="alerts" />;
}
