import en from "../../../messages/en.json";
import fa from "../../../messages/fa.json";
import { describe, expect, it } from "vitest";
import {
  getPublicApiErrorMessageKey,
  publicApiErrorCodes,
} from "./error-codes";

function resolveMessage(catalog: unknown, key: string): unknown {
  return key.split(".").reduce<unknown>((value, segment) => {
    if (typeof value !== "object" || value === null) return undefined;
    return (value as Record<string, unknown>)[segment];
  }, catalog);
}

describe("public API error messages", () => {
  it("maps every public API error code to both locales", () => {
    for (const code of publicApiErrorCodes) {
      const key = getPublicApiErrorMessageKey(code);
      expect(resolveMessage(en, key), `English: ${code}`).toEqual(
        expect.any(String),
      );
      expect(resolveMessage(fa, key), `Persian: ${code}`).toEqual(
        expect.any(String),
      );
    }
  });

  it("maps unrecognized codes to the generic public error", () => {
    expect(getPublicApiErrorMessageKey("unexpected_backend_code")).toBe(
      "publicErrors.unknown",
    );
  });
});
