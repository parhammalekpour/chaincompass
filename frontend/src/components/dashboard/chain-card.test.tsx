import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import en from "../../../messages/en.json";
import chainsFixture from "@/test/fixtures/chains.json";
import type { ChainDetailResponse, ChainSummary } from "@/lib/public-api/contracts";
import { ChainCard } from "./chain-card";
import { ReturnValue } from "@/components/app/return-value";

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

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const chains = chainsFixture.chains as ChainSummary[];

function renderWithMessages(children: ReactNode) {
  return render(
    <NextIntlClientProvider locale="en" messages={en}>
      {children}
    </NextIntlClientProvider>,
  );
}

describe("ChainCard", () => {
  it("keeps a score next to its confidence label", () => {
    renderWithMessages(<ChainCard chain={chains[0]} />);

    const score = screen.getByText("41.6 /100");
    expect(score).toBeVisible();
    expect(score.parentElement).toHaveTextContent("Medium");
    expect(screen.getByText("Medium")).toBeVisible();
  });

  it("shows partial coverage only when the latest score is partial", () => {
    const { unmount } = renderWithMessages(<ChainCard chain={chains[0]} />);
    expect(
      screen.getByRole("button", { name: "Partial coverage details" }),
    ).toBeVisible();
    unmount();

    renderWithMessages(<ChainCard chain={chains[1]} />);
    expect(
      screen.queryByRole("button", { name: "Partial coverage details" }),
    ).not.toBeInTheDocument();
  });

  it("opens the partial details tooltip on keyboard focus", async () => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
    const lastFullCoverage: NonNullable<
      ChainDetailResponse["last_full_coverage"]
    > = {
      value: "38.4",
      as_of_date: "2026-11-18",
      coverage: "0.7",
      confidence_label: "High",
    };
    renderWithMessages(
      <ChainCard chain={chains[0]} lastFullCoverage={lastFullCoverage} />,
    );

    fireEvent.focus(
      screen.getByRole("button", { name: "Partial coverage details" }),
    );

    const tooltip = await screen.findByRole("tooltip");
    expect(tooltip).toHaveTextContent(
      "Last full-coverage score: 38.4 on 2026-11-18.",
    );
  });

  it("shows the empty-history message for a null score", () => {
    renderWithMessages(<ChainCard chain={{ ...chains[0], score: null }} />);

    expect(screen.getByText("Not enough history yet")).toBeVisible();
  });

  it("shows signed returns with an arrow", () => {
    renderWithMessages(<ReturnValue value="-0.2534" />);

    expect(screen.getByText("-25.34% ↓")).toBeVisible();
    expect(screen.getByText("-25.34% ↓")).toHaveClass("text-danger");
  });

  it("shows overflow count for extra risk flags", () => {
    const chain = {
      ...chains[0],
      flags: Array.from({ length: 5 }, () => ({
        flag: "deep_drawdown",
        severity: "medium",
      })),
    };
    renderWithMessages(<ChainCard chain={chain} />);

    expect(screen.getByRole("button", { name: "+2 more" })).toBeVisible();
  });
});