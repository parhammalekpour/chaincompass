import { notFound } from "next/navigation";
import { PlaceholderPage } from "@/components/placeholder-page";
import { createPageMetadata } from "@/lib/metadata";
import { chains } from "@/lib/chains";

type Props = { params: Promise<{ locale: string; symbol: string }> };

export async function generateMetadata({ params }: Props) {
  const { locale, symbol } = await params;
  const chain = chains.find(
    (item) => item.symbol.toLowerCase() === symbol.toLowerCase(),
  );
  if (!chain) {
    return createPageMetadata("chainDetail", `/app/chains/${symbol}`, locale, {
      chainName: symbol.toUpperCase(),
    });
  }
  return createPageMetadata("chainDetail", `/app/chains/${symbol}`, locale, {
    chainName: chain.name[locale === "fa" ? "fa" : "en"],
  });
}

export default async function Page({ params }: Props) {
  const { symbol } = await params;
  const chain = chains.find(
    (item) => item.symbol.toLowerCase() === symbol.toLowerCase(),
  );
  if (!chain) notFound();

  return <PlaceholderPage namespace="chainDetail" values={{ chain: chain.symbol }} />;
}
