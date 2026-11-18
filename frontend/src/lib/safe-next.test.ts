import { describe, expect, it } from "vitest";
import { sanitizeNextPath } from "./safe-next";

describe("sanitizeNextPath", () => {
  it("adds the requested locale to an internal path", () => {
    expect(sanitizeNextPath("/app/settings", "fa")).toBe("/fa/app/settings");
  });

  it("keeps an existing supported locale prefix", () => {
    expect(sanitizeNextPath("/en/app?tab=profile", "fa")).toBe(
      "/en/app?tab=profile",
    );
  });

  it.each([
    "//evil.com",
    "https://attacker.example/path",
    "/\\evil.com",
    "https://evil.com",
    "%2F%2Fevil.com",
    "/%5Cevil.com",
    "/%2f%2fattacker.example",
    "/%252f%252fattacker.example",
    "/%5c%5cattacker.example",
    "javascript:alert(1)",
    "/%zz",
  ])("rejects unsafe next path %s", (value) => {
    expect(sanitizeNextPath(value, "fa")).toBe("/fa/app");
  });

  it("uses a safe fallback for missing paths", () => {
    expect(sanitizeNextPath(null, "en")).toBe("/en/app");
  });
});
