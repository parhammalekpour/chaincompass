import { LanguageSwitcher } from "@/components/language-switcher";
import { Compass } from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";

type Props = Readonly<{
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}>;

export default async function AuthLayout({
  children,
  params,
}: Props) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "common" });

  return (
    <main className="flex min-h-svh flex-col items-center justify-center px-5 py-10">
      <div className="absolute end-5 top-5">
        <LanguageSwitcher />
      </div>
      <Link href="/" className="mb-8 inline-flex items-center gap-2 text-lg font-semibold">
        <Compass className="size-5 text-primary" aria-hidden="true" />
        {t("appName")}
      </Link>
      <section className="w-full max-w-md rounded-2xl border border-border bg-surface p-6 shadow-xl sm:p-8">
        {children}
      </section>
      <Link href="/" className="mt-6 text-sm text-muted hover:text-foreground">
        {t("backHome")}
      </Link>
    </main>
  );
}
