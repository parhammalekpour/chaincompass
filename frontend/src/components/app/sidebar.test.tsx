import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi } from "vitest";
import en from "../../../messages/en.json";
import { Sidebar } from "./sidebar";

vi.mock("@/i18n/navigation", () => ({
  Link: ({
    href,
    children,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
  usePathname: () => "/app",
}));

describe("Sidebar", () => {
  it("renders all translated application links", () => {
    render(
      <NextIntlClientProvider locale="en" messages={en}>
        <Sidebar collapsed={false} />
      </NextIntlClientProvider>,
    );

    for (const label of [
      "Dashboard",
      "Chains",
      "Chat",
      "Watchlist",
      "Alerts",
      "Settings",
    ]) {
      expect(screen.getByRole("link", { name: label })).toBeVisible();
    }
  });
});
