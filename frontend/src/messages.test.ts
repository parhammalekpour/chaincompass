import { describe, expect, it } from "vitest";
import en from "../messages/en.json";
import fa from "../messages/fa.json";

function flattenKeys(value: unknown, prefix = ""): string[] {
  if (Array.isArray(value)) {
    return value.flatMap((nestedValue, index) =>
      flattenKeys(nestedValue, `${prefix}.${index}`),
    );
  }

  if (typeof value !== "object" || value === null) {
    return prefix ? [prefix] : [];
  }

  return Object.entries(value).flatMap(([key, nestedValue]) =>
    flattenKeys(nestedValue, prefix ? `${prefix}.${key}` : key),
  );
}

describe("message catalogs", () => {
  it("keeps English and Persian key sets in sync", () => {
    const englishKeys = new Set(flattenKeys(en));
    const persianKeys = new Set(flattenKeys(fa));
    const missingInPersian = [...englishKeys]
      .filter((key) => !persianKeys.has(key))
      .sort();
    const missingInEnglish = [...persianKeys]
      .filter((key) => !englishKeys.has(key))
      .sort();

    expect(
      missingInPersian,
      `Missing keys in messages/fa.json: ${missingInPersian.join(", ")}`,
    ).toEqual([]);
    expect(
      missingInEnglish,
      `Missing keys in messages/en.json: ${missingInEnglish.join(", ")}`,
    ).toEqual([]);
  });

  it("defines accessible labels and text alternatives for chain detail charts", () => {
    expect(en.chainDetail.scoreChartAccessibleLabel).toBeTruthy();
    expect(en.chainDetail.scoreChartTextAlternative).toBeTruthy();
    expect(en.chainDetail.priceChartAccessibleLabel).toBeTruthy();
    expect(en.chainDetail.priceChartTextAlternative).toBeTruthy();
    expect(fa.chainDetail.scoreChartAccessibleLabel).toBeTruthy();
    expect(fa.chainDetail.scoreChartTextAlternative).toBeTruthy();
    expect(fa.chainDetail.priceChartAccessibleLabel).toBeTruthy();
    expect(fa.chainDetail.priceChartTextAlternative).toBeTruthy();
  });

  it("avoids prohibited financial wording in both locales", () => {
    const englishText = JSON.stringify(en);
    const persianText = JSON.stringify(fa);
    const prohibitedEnglish =
      /\b(?:buy|buying|sell|selling|target|targets|predict|prediction|predictions|predictive|will|guarantee|guaranteed|guarantees)\b/i;
    const prohibitedPersian = /خرید|فروش|هدف|پیش[\u200c ]?بینی|تضمین|خواه(?:د|ند|ید)/;

    expect(englishText).not.toMatch(prohibitedEnglish);
    expect(persianText).not.toMatch(prohibitedPersian);
  });
});
