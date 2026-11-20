import { cleanup, render, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import en from "../../../messages/en.json";
import fa from "../../../messages/fa.json";
import chainsFixture from "@/test/fixtures/chains.json";
import { DashboardFrame } from "./dashboard-frame";
import { ChartDirectionWrapper } from "./chart-direction-wrapper";

vi.mock("./score-history-chart-loader", () => ({
  ScoreHistoryChartLoader: () => null,
}));

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

import { DashboardPage } from "./dashboard-page";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("dashboard direction and data states", () => {
  it("keeps the Persian page RTL and chart wrapper LTR", () => {
    const { container } = render(
      <NextIntlClientProvider locale="fa" messages={fa}>
        <DashboardFrame locale="fa">
          <ChartDirectionWrapper>
            <div>chart</div>
          </ChartDirectionWrapper>
        </DashboardFrame>
      </NextIntlClientProvider>,
    );

    expect(container.querySelector("section")).toHaveAttribute("dir", "rtl");
    expect(container.querySelector('[dir="ltr"]')).toHaveTextContent("chart");
  });

  it("removes the loading skeleton after chain data resolves", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        const body = url.endsWith("/api/v1/chains")
          ? chainsFixture
          : {
              generated_at: "2026-11-20T17:52:51.107921Z",
              analysis_only: true,
              slug: "btc",
              name: "Bitcoin",
              symbol: "BTC",
              price: chainsFixture.chains[0].price,
              score: { ...chainsFixture.chains[0].score, pillars: {}, components: [] },
              regime: chainsFixture.chains[0].regime,
              flags: [],
              freshness: chainsFixture.chains[0].freshness,
              last_full_coverage: {
                value: "38.4",
                as_of_date: "2026-11-18",
                coverage: "0.7",
                confidence_label: "High",
              },
              data_coverage: [],
              methodology_version: "v1",
            };
        return Promise.resolve(
          new Response(JSON.stringify(body), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }),
    );

    const { container } = render(
      <NextIntlClientProvider locale="en" messages={en}>
        <QueryClientProvider
          client={
            new QueryClient({
              defaultOptions: { queries: { retry: false } },
            })
          }
        >
          <DashboardPage />
        </QueryClientProvider>
      </NextIntlClientProvider>,
    );

    await waitFor(() => {
      expect(container.querySelector('[role="status"]')).not.toBeInTheDocument();
      expect(container.querySelector("h1")).toHaveTextContent("Dashboard");
    });
  });
});