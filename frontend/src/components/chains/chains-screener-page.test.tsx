import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import en from "../../../messages/en.json";
import chainsFixture from "@/test/fixtures/chains.json";
import { chainsResponseSchema } from "@/lib/public-api/contracts";
import * as publicApi from "@/lib/public-api/client";

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

import { ChainsScreenerPage } from "./chains-screener-page";

const chains = chainsResponseSchema.parse(chainsFixture);

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ChainsScreenerPage methodology link", () => {
  it("links the screener disclaimer to the Health Score methodology", async () => {
    vi.spyOn(publicApi, "getChains").mockResolvedValue(chains);
    render(
      <NextIntlClientProvider locale="en" messages={en}>
        <QueryClientProvider
          client={
            new QueryClient({
              defaultOptions: { queries: { retry: false } },
            })
          }
        >
          <ChainsScreenerPage />
        </QueryClientProvider>
      </NextIntlClientProvider>,
    );

    expect(
      await screen.findByRole("link", { name: "How this is computed" }),
    ).toHaveAttribute("href", "/methodology#health-score");
  });
});
