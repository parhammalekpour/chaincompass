import { createPageMetadata } from "@/lib/metadata";
import { SecuritySettings } from "@/components/app/security-settings";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return createPageMetadata("settings", "/app/settings", locale);
}

export default function Page() {
  return <SecuritySettings />;
}
