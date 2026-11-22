import { getTranslations } from "next-intl/server";
import {
  ChainNotFoundPage,
} from "@/components/chains/chain-detail-page";
import { FundamentalReportPage } from "@/components/chains/fundamental-report-page";
import { chainNameKeys } from "@/components/app/chain-labels";
import { createPageMetadata } from "@/lib/metadata";
import { chainSlugSchema } from "@/lib/public-api/contracts";

type Props = { params: Promise<{ locale: string; slug: string }> };

export async function generateMetadata({ params }: Props) {
  const { locale, slug } = await params;
  const parsedSlug = chainSlugSchema.safeParse(slug);
  const dashboardT = await getTranslations({
    locale,
    namespace: "dashboard",
  });
  const chainName = parsedSlug.success
    ? dashboardT(chainNameKeys[parsedSlug.data])
    : dashboardT("notAvailable");
  return createPageMetadata(
    "fundamentalReport",
    `/app/chains/${slug}/report`,
    locale,
    { chainName },
  );
}

export default async function Page({ params }: Props) {
  const { slug } = await params;
  const parsedSlug = chainSlugSchema.safeParse(slug);
  if (!parsedSlug.success) return <ChainNotFoundPage />;

  return <FundamentalReportPage slug={parsedSlug.data} />;
}
