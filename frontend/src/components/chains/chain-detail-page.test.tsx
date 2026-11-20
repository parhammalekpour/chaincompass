import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import en from "../../../messages/en.json";
import fa from "../../../messages/fa.json";
import chainFixture from "@/test/fixtures/btc-chain-detail.json";
import methodologyFixture from "@/test/fixtures/methodology-detail.json";
import priceFixture from "@/test/fixtures/btc-price-series.json";
import regimesFixture from "@/test/fixtures/btc-regimes.json";
import scenariosFixture from "@/test/fixtures/btc-scenarios.json";
import scoreHistoryFixture from "@/test/fixtures/btc-score-history-30d.json";
import {
  chainDetailResponseSchema,
  methodologyResponseSchema,
  regimesResponseSchema,
  scenariosResponseSchema,
  scoreHistoryResponseSchema,
  seriesResponseSchema,
} from "@/lib/public-api/contracts";
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

vi.mock("./chain-detail-charts-loader", () => ({
  ChainDetailChartsLoader: ({
    showScore,
    showPrice,
  }: {
    showScore: boolean;
    showPrice: boolean;
  }) => (
    <div
      data-testid={showScore ? "score-chart" : "price-chart"}
      data-show-price={String(showPrice)}
    />
  ),
}));

import {
  ChainDetailPage,
  ChainNotFoundPage,
} from "./chain-detail-page";

const detail = chainDetailResponseSchema.parse(chainFixture);
const scoreHistory = scoreHistoryResponseSchema.parse(scoreHistoryFixture);
const regimes = regimesResponseSchema.parse(regimesFixture);
const priceSeries = seriesResponseSchema.parse(priceFixture);
const scenarios = scenariosResponseSchema.parse(scenariosFixture);
const methodology = methodologyResponseSchema.parse(methodologyFixture);

function renderPage(locale: "en" | "fa" = "en") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={locale === "fa" ? fa : en}
    >
      <QueryClientProvider client={queryClient}>
        <ChainDetailPage slug="btc" />
      </QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

function mockSuccessfulQueries() {
  vi.spyOn(publicApi, "getChainDetail").mockResolvedValue(detail);
  vi.spyOn(publicApi, "getScoreHistory").mockResolvedValue(scoreHistory);
  vi.spyOn(publicApi, "getRegimes").mockResolvedValue(regimes);
  vi.spyOn(publicApi, "getSeries").mockResolvedValue(priceSeries);
  vi.spyOn(publicApi, "getScenarios").mockResolvedValue(scenarios);
  vi.spyOn(publicApi, "getMethodology").mockResolvedValue(methodology);
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

beforeEach(mockSuccessfulQueries);

describe("ChainDetailPage", () => {
  it("uses RTL for Persian content and LTR wrappers for charts and the timeline", async () => {
    renderPage("fa");

    await waitFor(() => {
      expect(screen.queryByRole("status", { name: "محتوا در حال بارگذاری است" }))
        .not.toBeInTheDocument();
    });

    expect(screen.getByRole("main")).toHaveAttribute("dir", "rtl");
    expect(screen.getByTestId("score-chart-wrapper")).toHaveAttribute(
      "dir",
      "ltr",
    );
    expect(screen.getByTestId("price-chart-wrapper")).toHaveAttribute(
      "dir",
      "ltr",
    );
    expect(screen.getByTestId("regime-timeline-wrapper")).toHaveAttribute(
      "dir",
      "ltr",
    );
  });

  it("keeps other sections rendered when one endpoint fails and removes resolved loading skeletons", async () => {
    vi.spyOn(publicApi, "getRegimes").mockRejectedValue(
      new publicApi.ApiError("network_error", 0),
    );
    const { container } = renderPage();

    expect(await screen.findByRole("alert")).toBeVisible();
    expect(screen.getByText("Bitcoin")).toBeVisible();
    expect(screen.getByTestId("score-chart")).toBeInTheDocument();
    expect(screen.getByTestId("price-chart")).toBeInTheDocument();
    expect(screen.getByText("Historical return quantiles, not a forecast."))
      .toBeVisible();
    await waitFor(() => {
      expect(
        container.querySelector('[role="status"][aria-label="Loading content"]'),
      ).not.toBeInTheDocument();
    });
  });

  it("renders a friendly not-found state for an invalid slug", () => {
    render(
      <NextIntlClientProvider locale="en" messages={en}>
        <ChainNotFoundPage />
      </NextIntlClientProvider>,
    );

    expect(screen.getByRole("heading", { name: "Chain not found" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Back to chains" })).toHaveAttribute(
      "href",
      "/app/chains",
    );
  });
});
