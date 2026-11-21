"use client";

import { useLocale, useTranslations } from "next-intl";
import { ContentTable } from "@/components/marketing/content-table";

const TOC_KEYS = ["terms", "privacy", "cookies", "sources", "contact"] as const;

export function LegalPage() {
  const locale = useLocale();
  const t = useTranslations("legalPage");

  return (
    <main
      lang={locale}
      dir={locale === "fa" ? "rtl" : "ltr"}
      className="mx-auto max-w-3xl space-y-10 px-4 py-10 sm:px-6 sm:py-14"
    >
      <header className="space-y-4">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          {t("title")}
        </h1>
        <p className="leading-7 text-muted">{t("intro")}</p>
      </header>

      <nav
        aria-label={t("tocLabel")}
        className="rounded-xl border border-border bg-surface p-5"
      >
        <h2 className="font-semibold">{t("tocLabel")}</h2>
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {TOC_KEYS.map((key) => (
            <li key={key}>
              <a
                className="text-primary underline-offset-4 hover:underline"
                href={`#${key}`}
              >
                {t(`toc.${key}`)}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <section id="terms" className="scroll-mt-24 space-y-3">
        <h2 className="text-2xl font-semibold">{t("sections.terms.title")}</h2>
        <p className="leading-7 text-muted">{t("sections.terms.asIs")}</p>
        <p className="leading-7 text-muted">
          {t("sections.terms.responsibility")}
        </p>
        <p className="leading-7 text-muted">
          {t("sections.terms.thirdParty")}
        </p>
        <p className="leading-7 text-muted">
          {t("sections.terms.acceptableUse")}
        </p>
        <p className="leading-7 text-muted">{t("sections.terms.changes")}</p>
        <p className="leading-7 text-muted">{t("sections.terms.notAvailable")}</p>
      </section>

      <section id="privacy" className="scroll-mt-24 space-y-4">
        <h2 className="text-2xl font-semibold">{t("sections.privacy.title")}</h2>
        <p className="leading-7 text-muted">{t("sections.privacy.intro")}</p>
        <ContentTable
          caption={t("sections.privacy.tableCaption")}
          headings={[
            t("sections.privacy.itemHeading"),
            t("sections.privacy.purposeHeading"),
          ]}
        >
          {(
            [
              ["email", "emailPurpose"],
              ["password", "passwordPurpose"],
              ["role", "rolePurpose"],
              ["refresh", "refreshPurpose"],
              ["emailTokens", "emailTokensPurpose"],
              ["external", "externalPurpose"],
            ] as const
          ).map(([item, purpose]) => (
            <tr key={item} className="align-top">
              <td className="px-3 py-3 leading-6 text-muted">
                {t(`sections.privacy.${item}`)}
              </td>
              <td className="px-3 py-3 leading-6 text-muted">
                {t(`sections.privacy.${purpose}`)}
              </td>
            </tr>
          ))}
        </ContentTable>
        <p className="leading-7 text-muted">
          {t("sections.privacy.conversations")}
        </p>
        <p className="leading-7 text-muted">{t("sections.privacy.usage")}</p>
        <p className="leading-7 text-muted">
          {t("sections.privacy.aiProvider")}
        </p>
        <p className="leading-7 text-muted">
          {t("sections.privacy.publicData")}
        </p>
      </section>

      <section id="cookies" className="scroll-mt-24 space-y-4">
        <h2 className="text-2xl font-semibold">{t("sections.cookies.title")}</h2>
        <p className="leading-7 text-muted">{t("sections.cookies.intro")}</p>
        <ContentTable
          caption={t("sections.cookies.cookieCaption")}
          headings={[
            t("sections.cookies.nameHeading"),
            t("sections.cookies.purposeHeading"),
          ]}
        >
          {(
            [
              ["refreshCookie", "refreshPurpose"],
              ["csrfCookie", "csrfPurpose"],
              ["localeCookie", "localePurpose"],
              ["oauthCookie", "oauthPurpose"],
            ] as const
          ).map(([name, purpose]) => (
            <tr key={name} className="align-top">
              <th scope="row" className="px-3 py-3 text-start font-medium">
                <code dir="ltr">{t(`sections.cookies.${name}`)}</code>
              </th>
              <td className="px-3 py-3 leading-6 text-muted">
                {t(`sections.cookies.${purpose}`)}
              </td>
            </tr>
          ))}
        </ContentTable>
        <ContentTable
          caption={t("sections.cookies.storageCaption")}
          headings={[
            t("sections.cookies.storageNameHeading"),
            t("sections.cookies.storagePurposeHeading"),
          ]}
        >
          {(
            [
              ["themeKey", "themePurpose"],
              ["sidebarKey", "sidebarPurpose"],
              ["logoutKey", "logoutPurpose"],
            ] as const
          ).map(([name, purpose]) => (
            <tr key={name} className="align-top">
              <th scope="row" className="px-3 py-3 text-start font-medium">
                <code dir="ltr">{t(`sections.cookies.${name}`)}</code>
              </th>
              <td className="px-3 py-3 leading-6 text-muted">
                {t(`sections.cookies.${purpose}`)}
              </td>
            </tr>
          ))}
        </ContentTable>
        <p className="leading-7 text-muted">
          {t("sections.cookies.accessToken")}
        </p>
      </section>

      <section id="sources" className="scroll-mt-24 space-y-3">
        <h2 className="text-2xl font-semibold">{t("sections.sources.title")}</h2>
        <p className="leading-7 text-muted">{t("sections.sources.body")}</p>
        <p className="leading-7 text-muted">
          {t("sections.sources.emailProvider")}
        </p>
        <p className="leading-7 text-muted">
          {t("sections.sources.accountDeletion")}
        </p>
        <p className="leading-7 text-muted">{t("sections.sources.contact")}</p>
      </section>

      <section id="contact" className="scroll-mt-24 space-y-3">
        <h2 className="text-2xl font-semibold">{t("sections.contact.title")}</h2>
        <a
          href="https://github.com/parhammalekpour/chaincompass/issues"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex text-primary underline-offset-4 hover:underline"
        >
          {t("sections.contact.linkLabel")}
        </a>
        <p className="text-sm text-muted">
          {t("sections.contact.lastUpdated")}:{" "}
          <time dateTime="2026-11-21" dir="ltr">
            {t("sections.contact.date")}
          </time>
        </p>
      </section>
    </main>
  );
}
