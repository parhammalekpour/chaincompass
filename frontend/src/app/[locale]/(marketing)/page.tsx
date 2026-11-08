import { LandingPage } from "@/components/marketing/landing-page";
import { createPageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return createPageMetadata("landing", "/", locale);
}

export default function Page() {
  return <LandingPage />;
}
