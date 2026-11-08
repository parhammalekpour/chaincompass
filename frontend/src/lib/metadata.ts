import type { Metadata } from "next";
import { hasLocale } from "next-intl";
import en from "../../messages/en.json";
import fa from "../../messages/fa.json";
import { routing } from "@/i18n/routing";

type MetadataValues = Record<string, string>;

export async function createPageMetadata(
  page: keyof typeof en.metadata,
  pathname: string,
  locale: string,
  values?: MetadataValues,
): Promise<Metadata> {
  if (!hasLocale(routing.locales, locale)) {
    throw new Error(`Unsupported locale for metadata: ${locale}`);
  }
  const messages = locale === "fa" ? fa : en;
  const localizedPath = pathname === "/" ? "" : pathname;
  const urlFor = (targetLocale: string) => `/${targetLocale}${localizedPath}`;
  const pageMessages = messages.metadata[page];
  if (typeof pageMessages === "string") {
    throw new Error(`Metadata page is missing: ${page}`);
  }
  const interpolate = (text: string) =>
    text.replace(/\{(\w+)\}/g, (match, key: string) => values?.[key] ?? match);

  return {
    title: interpolate(pageMessages.title),
    description: interpolate(pageMessages.description),
    alternates: {
      canonical: urlFor(locale),
      languages: {
        en: urlFor("en"),
        fa: urlFor("fa"),
        "x-default": urlFor(routing.defaultLocale),
      },
    },
  };
}

export function getMetadataBase() {
  return new URL(process.env.APP_BASE_URL ?? "http://localhost:3000");
}
