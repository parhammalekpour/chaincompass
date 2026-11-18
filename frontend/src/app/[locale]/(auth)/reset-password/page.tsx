import { ResetPasswordForm } from "@/components/auth/reset-password-form";
import { createPageMetadata } from "@/lib/metadata";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return createPageMetadata("resetPassword", "/reset-password", locale);
}

export default function Page() {
  return <ResetPasswordForm />;
}
