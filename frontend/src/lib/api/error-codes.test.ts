import en from "../../../messages/en.json";
import fa from "../../../messages/fa.json";
import { describe, expect, it } from "vitest";
import {
  backendErrorCodes,
  backendErrorMessageKeys,
} from "./error-codes";

function sortedKeys(value: unknown): string[] {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return [];
  }
  return Object.keys(value).sort();
}

function nestedKeyPaths(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return [prefix];
  }
  return Object.entries(value).flatMap(([key, child]) =>
    nestedKeyPaths(child, prefix ? `${prefix}.${key}` : key),
  );
}

describe("error translation coverage", () => {
  it("maps every checked-in backend error code to an English and Persian key", () => {
    for (const code of backendErrorCodes) {
      const messageKey = backendErrorMessageKeys[code].replace(
        "authErrors.",
        "",
      );
      expect(en.authErrors).toHaveProperty(messageKey);
      expect(fa.authErrors).toHaveProperty(messageKey);
    }
  });

  it("keeps English and Persian message key structures identical", () => {
    expect(nestedKeyPaths(en)).toEqual(nestedKeyPaths(fa));
  });

  it("has an error mapping for each checked-in backend code", () => {
    expect(sortedKeys(backendErrorMessageKeys).sort()).toEqual(
      [...backendErrorCodes].sort(),
    );
  });
});
