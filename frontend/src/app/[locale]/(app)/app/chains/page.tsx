import { ChainsScreenerPage } from "@/components/chains/chains-screener-page";
import { createPageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return createPageMetadata("chains", "/app/chains", locale);
}

export default function Page() {
  return <ChainsScreenerPage />;
}
