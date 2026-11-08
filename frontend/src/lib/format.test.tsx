import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Num } from "@/components/num";
import {
  formatCompact,
  formatCurrency,
  formatNumber,
  formatPercent,
} from "./format";

afterEach(cleanup);

const locales = ["en", "fa"] as const;
const nonLatinDigits = /[\u0660-\u0669\u06f0-\u06f9]/;

describe("number formatters", () => {
  it.each(locales)("uses Latin digits for numbers in %s", (locale) => {
    const formatted = formatNumber(12345.6, locale);

    expect(formatted).toMatch(/[0-9]/);
    expect(formatted).not.toMatch(nonLatinDigits);
  });

  it.each(locales)("formats currency with Latin digits in %s", (locale) => {
    const formatted = formatCurrency(1234.5, locale, "USD");

    expect(formatted).toMatch(/1,234\.50/);
    expect(formatted).not.toMatch(nonLatinDigits);
  });

  it.each(locales)("formats percentages with Latin digits in %s", (locale) => {
    const formatted = formatPercent(0.125, locale);

    expect(formatted).toContain("12.5");
    expect(formatted).toMatch(/%/);
    expect(formatted).not.toMatch(nonLatinDigits);
  });

  it("formats compact values with Latin digits", () => {
    const formatted = formatCompact(1200, "fa");

    expect(formatted).toContain("1.2");
    expect(formatted).not.toMatch(nonLatinDigits);
  });
});

describe("Num", () => {
  it("keeps Persian numeric content isolated with tabular digits", () => {
    render(<Num value={1234.5} locale="fa" format="currency" />);

    const number = screen.getByText((_, element) => {
      return (
        element?.tagName.toLowerCase() === "span" &&
        element.getAttribute("dir") === "ltr"
      );
    });

    expect(number).toHaveAttribute("dir", "ltr");
    expect(number).toHaveClass("tabular-nums");
    expect(number.textContent).not.toMatch(nonLatinDigits);
  });
});
