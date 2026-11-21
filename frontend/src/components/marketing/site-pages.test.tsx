import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import en from "../../../messages/en.json";
import fa from "../../../messages/fa.json";
import { LegalPage } from "./legal-page";
import { MethodologyPage } from "./methodology-page";
import { SiteFooter } from "@/components/site-footer";
import { getMethodology } from "@/lib/public-api/client";
import { methodologyResponseSchema } from "@/lib/public-api/contracts";
import methodologyFixture from "@/test/fixtures/methodology-detail.json";
import sitemap from "@/app/sitemap";

vi.mock("@/i18n/navigation", () => ({
  Link: ({
    href,
    children,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href as string} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/components/language-switcher", () => ({
  LanguageSwitcher: () => null,
}));

vi.mock("@/lib/public-api/client", () => ({
  getMethodology: vi.fn(),
}));

const methodology = methodologyResponseSchema.parse(methodologyFixture);

function renderLocalized(locale: "en" | "fa", children: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={locale === "en" ? en : fa}
    >
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

function expectOneHeadingAndResolvedToc(container: HTMLElement) {
  expect(container.querySelectorAll("h1")).toHaveLength(1);
  for (const link of container.querySelectorAll<HTMLAnchorElement>(
    'nav a[href^="#"]',
  )) {
    expect(container.querySelector(link.hash)).not.toBeNull();
  }
}

describe("public methodology and legal pages", () => {
  beforeEach(() => {
    vi.mocked(getMethodology).mockResolvedValue(methodology);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it.each([
    ["en", "ltr"],
    ["fa", "rtl"],
  ] as const)(
    "renders methodology in %s with accessible structure",
    async (locale, dir) => {
      const { container } = renderLocalized(locale, <MethodologyPage />);
      const main = container.querySelector("main");

      expect(main).toHaveAttribute("lang", locale);
      expect(main).toHaveAttribute("dir", dir);
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        locale === "en" ? "Methodology" : "روش‌شناسی",
      );
      expect(container.querySelectorAll("table caption")).not.toHaveLength(0);
      expect(container.querySelectorAll("table th[scope]")).not.toHaveLength(0);
      expectOneHeadingAndResolvedToc(container);
      expect(container.textContent).not.toMatch(/[۰-۹٠-٩]/);
      expect(
        [...container.querySelectorAll("code")].every(
          (code) => code.getAttribute("dir") === "ltr",
        ),
      ).toBe(true);
      expect(main?.querySelector(".animate-pulse")).toBeNull();
      expect(container.textContent).toContain(
        locale === "en"
          ? "Pooled non-overlapping 30-day p10-p90 hit rates"
          : "نرخ پوشش p10-p90",
      );
    },
  );

  it.each([
    ["en", "ltr"],
    ["fa", "rtl"],
  ] as const)(
    "renders legal information in %s with accessible structure",
    (locale, dir) => {
      const { container } = renderLocalized(locale, <LegalPage />);
      const main = container.querySelector("main");

      expect(main).toHaveAttribute("lang", locale);
      expect(main).toHaveAttribute("dir", dir);
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        locale === "en" ? "Legal and privacy" : "اطلاعات حقوقی و حریم خصوصی",
      );
      expect(container.querySelectorAll("table caption")).not.toHaveLength(0);
      expect(container.querySelectorAll("table th[scope]")).not.toHaveLength(0);
      expectOneHeadingAndResolvedToc(container);
      expect(container.textContent).not.toMatch(/[۰-۹٠-٩]/);
      expect(
        [...container.querySelectorAll("code")].every(
          (code) => code.getAttribute("dir") === "ltr",
        ),
      ).toBe(true);
      expect(main?.querySelector(".animate-pulse")).toBeNull();
    },
  );

  it("uses methodology endpoint pillar weights and documents a static fallback", async () => {
    const healthScore = readFileSync(
      resolve(process.cwd(), "../docs/HEALTH_SCORE.md"),
      "utf8",
    );
    const expectedWeights = [
      ...healthScore.matchAll(
        /^\|\s*(Adoption|Capital|Security & economics|Market condition)\s*\|\s*(\d+)\s*\|$/gm,
      ),
    ];
    expect(expectedWeights).toHaveLength(4);
    const { container } = renderLocalized("en", <MethodologyPage />);

    for (const [, pillar, weight] of expectedWeights) {
      const displayedPillar =
        pillar === "Security & economics" ? "Security and economics" : pillar;
      await waitFor(() => {
        expect(
          screen.getByRole("row", {
            name: new RegExp(`${displayedPillar} ${weight}`),
          }),
        ).toBeInTheDocument();
      });
    }
    const coverageMatch = healthScore.match(
      /Registry-\s*derived maximum coverage is BTC `([\d.]+)`, ETH `([\d.]+)`, SOL `([\d.]+)`, and BNB `([\d.]+)`/,
    );
    expect(coverageMatch).not.toBeNull();
    for (const [chain, value] of [
      ["BTC", coverageMatch?.[1]],
      ["ETH", coverageMatch?.[2]],
      ["SOL", coverageMatch?.[3]],
      ["BNB", coverageMatch?.[4]],
    ] as const) {
      expect(
        screen.getByRole("row", { name: `${chain} ${value}` }),
      ).toBeInTheDocument();
    }
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/[۰-۹٠-٩]/);
  });

  it("keeps a visible static weights fallback when the methodology API fails", async () => {
    vi.mocked(getMethodology).mockRejectedValue(new Error("offline"));
    renderLocalized("en", <MethodologyPage />);

    expect(
      await screen.findByText(
        "The methodology endpoint could not be reached. The table shows the documented v1 fallback values.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("row", { name: "Adoption 30" }),
    ).toBeInTheDocument();
  });

  it.each(["full", "compact"] as const)(
    "lists all six attributed sources as safe external links in the %s footer",
    (variant) => {
      renderLocalized("en", <SiteFooter variant={variant} />);

      for (const source of Object.values(en.siteFooter.sourceNames)) {
        const link = screen.getByRole("link", {
          name: en.siteFooter.visitSource.replace("{source}", source),
        });
        expect(link).toHaveAttribute("target", "_blank");
        expect(link).toHaveAttribute("rel", "noopener noreferrer");
      }
      expect(
        screen.getByRole("link", { name: "Methodology" }),
      ).toHaveAttribute("href", "/methodology");
      expect(screen.getByRole("link", { name: "Legal" })).toHaveAttribute(
        "href",
        "/legal",
      );
    },
  );

  it("includes each localized methodology and legal route once in the sitemap", () => {
    const urls = sitemap().map(({ url }) => new URL(url).pathname);

    for (const path of [
      "/en/methodology",
      "/fa/methodology",
      "/en/legal",
      "/fa/legal",
    ]) {
      expect(urls.filter((url) => url === path)).toHaveLength(1);
    }
  });
});
