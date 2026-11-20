import { cleanup, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import en from "../../messages/en.json";
import fa from "../../messages/fa.json";
import { PlaceholderPage } from "./placeholder-page";

vi.mock("@/i18n/navigation", () => ({
  Link: ({
    href,
    children,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & {
    href: string;
    children: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

afterEach(cleanup);

describe("placeholder page", () => {
  it.each([
    ["chat", "en", en, "Coming soon", "Back to dashboard"],
    ["watchlist", "en", en, "Coming soon", "Back to dashboard"],
    ["alerts", "en", en, "Coming soon", "Back to dashboard"],
    ["chainDetail", "en", en, "Coming soon", "Back to dashboard"],
    ["chat", "fa", fa, "به‌زودی", "بازگشت به نمای کلی"],
    ["watchlist", "fa", fa, "به‌زودی", "بازگشت به نمای کلی"],
    ["alerts", "fa", fa, "به‌زودی", "بازگشت به نمای کلی"],
    ["chainDetail", "fa", fa, "به‌زودی", "بازگشت به نمای کلی"],
  ] as const)(
    "renders a localized coming-soon card for %s in %s",
    (namespace, locale, messages, title, back) => {
      render(
        <NextIntlClientProvider locale={locale} messages={messages}>
          <PlaceholderPage
            namespace={namespace}
            values={
              namespace === "chainDetail"
                ? { chain: "Bitcoin" }
                : undefined
            }
          />
        </NextIntlClientProvider>,
      );

      expect(screen.getByRole("heading", { name: title })).toBeVisible();
      expect(screen.getByRole("link", { name: back })).toHaveAttribute(
        "href",
        "/app",
      );
      expect(screen.queryByRole("status")).not.toBeInTheDocument();
    },
  );
});
