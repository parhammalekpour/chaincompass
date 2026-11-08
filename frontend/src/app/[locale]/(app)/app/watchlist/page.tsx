import { PlaceholderPage } from "@/components/placeholder-page";
import { createPageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return createPageMetadata("watchlist", "/app/watchlist", locale);
}

export default function Page() {
  return <PlaceholderPage namespace="watchlist" />;
}
