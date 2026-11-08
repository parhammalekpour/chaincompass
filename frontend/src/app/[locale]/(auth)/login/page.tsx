import { PlaceholderPage } from "@/components/placeholder-page";
import { createPageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return createPageMetadata("login", "/login", locale);
}

export default function Page() {
  return <PlaceholderPage namespace="login" compact />;
}
