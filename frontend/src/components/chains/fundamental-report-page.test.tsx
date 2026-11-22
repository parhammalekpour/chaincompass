import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import en from "../../../messages/en.json";
import fa from "../../../messages/fa.json";
import fundamentalReportFixture from "@/test/fixtures/fundamental-report.json";
import { ApiError } from "@/lib/public-api/client";
import type { ChainSlug } from "@/lib/public-api/contracts";
import { fundamentalReportResponseSchema } from "@/lib/public-api/contracts";
import * as publicApi from "@/lib/public-api/client";
import { FundamentalReportPage } from "./fundamental-report-page";

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

const report = fundamentalReportResponseSchema.parse(fundamentalReportFixture);

function renderReport(
  locale: "en" | "fa" = "en",
  slug: ChainSlug = "eth",
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={locale === "fa" ? fa : en}
    >
      <QueryClientProvider client={queryClient}>
        <FundamentalReportPage slug={slug} />
      </QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

function mockReport(value = report) {
  vi.spyOn(publicApi, "getFundamentalReport").mockResolvedValue(value);
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("FundamentalReportPage", () => {
  it("renders all report sections, neutral changes, and fixed data gaps", async () => {
    mockReport();
    const { container } = renderReport();

    expect(
      await screen.findByRole("heading", {
        name: "Fundamental report for Ethereum",
      }),
    ).toBeVisible();
    expect(screen.getByText("Descriptive and historical data only; not a forecast."))
      .toBeVisible();
    expect(screen.getByRole("heading", { name: "Health" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Regime" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Active flags" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Indicators" })).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "What we do not know" }),
    ).toBeVisible();
    expect(screen.getByRole("table").querySelector("caption")).toHaveTextContent(
      "Stored Health Score components",
    );
    expect(screen.getAllByText("Not available from free verified sources"))
      .toHaveLength(3);
    for (const key of [
      "holder_distribution",
      "exchange_flows",
      "news_evidence",
    ]) {
      expect(screen.getByText(key)).toBeVisible();
    }

    const scoreChange = screen.getByTestId("score-change-30d");
    expect(scoreChange).toHaveTextContent("+1.50");
    expect(scoreChange.className).not.toMatch(/text-(success|danger|green|red)/);
    expect(container.querySelectorAll("th[scope='col']")).toHaveLength(4);
    expect(container.querySelectorAll("th[scope='row']")).not.toHaveLength(0);
  });

  it("shows a specific message when an exact stored score is missing", async () => {
    mockReport({
      ...report,
      health: {
        ...report.health,
        score_30d_ago: null,
        score_90d_ago: null,
        change_30d: null,
        change_90d: null,
      },
    });
    renderReport();

    expect(
      await screen.findAllByText("Not enough stored history"),
    ).toHaveLength(2);
  });

  it("shows the regime history gap note only when the response says it exists", async () => {
    mockReport();
    const first = renderReport();
    await screen.findByRole("heading", {
      name: "Fundamental report for Ethereum",
    });
    expect(
      screen.queryByText(
        "Regime history contains a gap. The start date and duration refer to the latest consecutive run.",
      ),
    ).not.toBeInTheDocument();
    first.unmount();

    vi.restoreAllMocks();
    mockReport({
      ...report,
      regime: { ...report.regime, history_gap: true },
    });
    renderReport();
    expect(
      await screen.findByText(
        "Regime history contains a gap. The start date and duration refer to the latest consecutive run.",
      ),
    ).toBeVisible();
  });

  it("labels unavailable and inapplicable indicators in both text and icon", async () => {
    mockReport();
    const { container } = renderReport();

    expect(await screen.findAllByText("Not available")).not.toHaveLength(0);
    expect(screen.getAllByText("Not applicable")).not.toHaveLength(0);
    expect(
      container.querySelectorAll("td svg[aria-hidden='true']").length,
    ).toBeGreaterThan(0);
  });

  it("renders explicit empty states for flags and data gaps", async () => {
    mockReport({ ...report, flags: [], data_gaps: [] });
    renderReport();

    expect(await screen.findByText("No active flags")).toBeVisible();
    expect(screen.getByText("No additional data gaps are recorded.")).toBeVisible();
  });

  it("renders Persian RTL layout with Latin digits and a fixed assistant link", async () => {
    mockReport();
    const { container } = renderReport("fa");
    const main = await screen.findByRole("main");

    expect(main).toHaveAttribute("dir", "rtl");
    expect(container.textContent).not.toMatch(/[۰-۹٠-٩]/);
    expect(
      screen.getByRole("link", { name: "توضیح با دستیار" }),
    ).toHaveAttribute("href", "/app/chat?ask=report&chain=eth");
  });

  it("shows dedicated unavailable and unknown-chain states", async () => {
    vi.spyOn(publicApi, "getFundamentalReport").mockRejectedValue(
      new ApiError("report_not_available", 404),
    );
    const notAvailable = renderReport();
    expect(
      await screen.findByText(
        "A stored fundamental report is not available for this chain and date.",
      ),
    ).toBeVisible();
    notAvailable.unmount();

    vi.restoreAllMocks();
    vi.spyOn(publicApi, "getFundamentalReport").mockRejectedValue(
      new ApiError("chain_not_found", 404),
    );
    renderReport();
    expect(
      await screen.findByRole("heading", { name: "Chain not found" }),
    ).toBeVisible();
  });

  it("shows a loading skeleton while the report request is pending", async () => {
    let resolveReport: ((value: typeof report) => void) | undefined;
    vi.spyOn(publicApi, "getFundamentalReport").mockReturnValue(
      new Promise((resolve) => {
        resolveReport = resolve;
      }),
    );
    renderReport();

    expect(screen.getByRole("status", { name: "Loading content" })).toBeVisible();
    resolveReport?.(report);
    await waitFor(() =>
      expect(
        screen.getByRole("heading", {
          name: "Fundamental report for Ethereum",
        }),
      ).toBeVisible(),
    );
  });
});
