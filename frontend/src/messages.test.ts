import { describe, expect, it } from "vitest";
import en from "../messages/en.json";
import fa from "../messages/fa.json";

function flattenKeys(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
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
});
