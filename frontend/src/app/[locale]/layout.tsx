import "@fontsource-variable/inter";
import "@fontsource-variable/vazirmatn";
import type { Metadata } from "next";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { ThemeProvider } from "@/components/theme-provider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { getMetadataBase } from "@/lib/metadata";
import { routing } from "@/i18n/routing";
import "./../globals.css";

type LocaleLayoutProps = Readonly<{
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}>;

export const dynamic = "force-static";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: Pick<LocaleLayoutProps, "params">): Promise<Metadata> {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }
  const t = await getTranslations({ locale, namespace: "metadata" });

  return {
    metadataBase: getMetadataBase(),
    title: {
      default: t("siteTitle"),
      template: `%s | ${t("brand")}`,
    },
    description: t("siteDescription"),
    alternates: {
      canonical: `/${locale}`,
      languages: {
        en: "/en",
        fa: "/fa",
        "x-default": "/en",
      },
    },
  };
}

export default async function LocaleLayout({
  children,
  params,
}: LocaleLayoutProps) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }
  setRequestLocale(locale);
  const messages = await getMessages({ locale });
  const direction = locale === "fa" ? "rtl" : "ltr";

  return (
    <html
      lang={locale}
      dir={direction}
      className={`${locale === "fa" ? "font-fa" : "font-en"} dark`}
      suppressHydrationWarning
    >
      <body className="min-h-svh bg-background text-foreground antialiased">
        <NextIntlClientProvider locale={locale} messages={messages}>
          <ThemeProvider>
            <TooltipProvider>
              {children}
              <Toaster />
            </TooltipProvider>
          </ThemeProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
