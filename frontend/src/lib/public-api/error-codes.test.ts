import en from "../../../messages/en.json";
import fa from "../../../messages/fa.json";
import { describe, expect, it } from "vitest";
import {
  getPublicApiErrorMessage,
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

  it("uses a localized duration when a valid Retry-After value exists", () => {
    expect(getPublicApiErrorMessage("rate_limited", "30", "en")).toEqual({
      key: "publicErrors.rateLimitedRetry",
      values: { retryAfter: "30 seconds" },
    });
    expect(getPublicApiErrorMessage("rate_limited", "75", "fa")).toEqual({
      key: "publicErrors.rateLimitedRetry",
      values: { retryAfter: "1 دقیقه و 15 ثانیه" },
    });
  });

  it.each([undefined, "not-a-duration", "0", "-2"])(
    "uses the plain rate-limit message without a valid duration (%s)",
    (retryAfter) => {
      expect(
        getPublicApiErrorMessage("rate_limited", retryAfter, "en"),
      ).toEqual({ key: "publicErrors.rateLimited" });
    },
  );
});
