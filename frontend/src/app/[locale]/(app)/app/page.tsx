import { DashboardPage } from "@/components/dashboard/dashboard-page";
import { createPageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return createPageMetadata("dashboard", "/app", locale);
}

export default function Page() {
  return <DashboardPage />;
}
