import { getTranslations } from "next-intl/server";
import {
  ChainDetailPage,
  ChainNotFoundPage,
} from "@/components/chains/chain-detail-page";
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
  const detailT = await getTranslations({
    locale,
    namespace: "chainDetail",
  });
  const chainName = parsedSlug.success
    ? dashboardT(chainNameKeys[parsedSlug.data])
    : detailT("notFoundTitle");
  return createPageMetadata("chainDetail", `/app/chains/${slug}`, locale, {
    chainName,
  });
}

export default async function Page({ params }: Props) {
  const { slug } = await params;
  const parsedSlug = chainSlugSchema.safeParse(slug);
  if (!parsedSlug.success) return <ChainNotFoundPage />;

  return <ChainDetailPage slug={parsedSlug.data} />;
}
