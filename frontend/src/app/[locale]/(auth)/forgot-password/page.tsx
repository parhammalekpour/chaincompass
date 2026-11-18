import { ForgotPasswordForm } from "@/components/auth/forgot-password-form";
import { createPageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return createPageMetadata("forgotPassword", "/forgot-password", locale);
}

export default function Page() {
  return <ForgotPasswordForm />;
}
