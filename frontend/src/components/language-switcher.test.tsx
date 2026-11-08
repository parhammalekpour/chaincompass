import { afterEach, describe, expect, it, vi } from "vitest";
import {
  changeLocale,
  getLocaleTargetPath,
} from "@/lib/locale-navigation";

afterEach(() => {
  document.cookie = "NEXT_LOCALE=; Path=/; Max-Age=0";
});

describe("language switcher navigation", () => {
  it("keeps the path and query while changing only the locale prefix", () => {
    expect(
      getLocaleTargetPath("/app/alerts", "?range=week&kind=risk", "fa"),
    ).toBe("/fa/app/alerts?range=week&kind=risk");
  });

  it("sets the locale cookie and navigates to the matching localized path", () => {
    const navigate = vi.fn();

    changeLocale("/methodology", "?section=scores", "fa", navigate);

    expect(document.cookie).toContain("NEXT_LOCALE=fa");
    expect(navigate).toHaveBeenCalledWith("/fa/methodology?section=scores");
  });
});
