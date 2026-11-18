import { GoogleCallback } from "@/components/auth/google-callback";
import { createPageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return createPageMetadata("authCallback", "/auth/callback", locale);
}

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return <GoogleCallback locale={locale === "fa" ? "fa" : "en"} />;
}
