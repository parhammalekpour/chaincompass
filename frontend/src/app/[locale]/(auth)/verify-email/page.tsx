import { VerifyEmailPage } from "@/components/auth/verify-email-page";
import { createPageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return createPageMetadata("verifyEmail", "/verify-email", locale);
}

export default function Page() {
  return <VerifyEmailPage />;
}
