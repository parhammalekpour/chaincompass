import { afterEach, describe, expect, it, vi } from "vitest";
import fundamentalReportFixture from "@/test/fixtures/fundamental-report.json";
import {
  ContractError,
  getChains,
  getChainDetail,
  getFundamentalReport,
  getScoreHistory,
} from "./client";
import type { ChainSlug } from "./contracts";

function jsonResponse(
  body: unknown,
  status = 200,
  headers?: HeadersInit,
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("public API client", () => {
  it("uses same-origin public GET requests without auth headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        generated_at: "2026-11-20T17:52:51.107921Z",
        analysis_only: true,
        chains: [],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await getChains();

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/chains");
    expect(options.method).toBe("GET");
    expect(options.credentials).toBe("omit");
    expect(new Headers(options.headers).get("Authorization")).toBeNull();
  });

  it("maps 429 and preserves Retry-After text", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          { error: { code: "rate_limited", message: "private details" } },
          429,
          { "Retry-After": "17" },
        ),
      ),
    );

    await expect(getChains()).rejects.toMatchObject({
      name: "ApiError",
      code: "rate_limited",
      status: 429,
      retryAfter: "17",
    });
  });

  it("maps chain 404 errors without exposing the server message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          { error: { code: "chain_not_found", message: "private detail" } },
          404,
        ),
      ),
    );

    await expect(getChainDetail("btc")).rejects.toMatchObject({
      name: "ApiError",
      code: "chain_not_found",
      status: 404,
    });
  });

  it("maps report 404 errors without exposing the server message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "report_not_available",
              message: "private detail",
            },
          },
          404,
        ),
      ),
    );

    await expect(getFundamentalReport("eth")).rejects.toMatchObject({
      name: "ApiError",
      code: "report_not_available",
      status: 404,
    });
  });

  it("loads the typed report from the same-origin chain endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(fundamentalReportFixture),
    );
    vi.stubGlobal("fetch", fetchMock);

    const report = await getFundamentalReport("eth");

    expect(report.as_of_date).toBe("2026-11-20");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/chains/eth/report",
      expect.any(Object),
    );
  });

  it("maps a network failure to network_error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    await expect(getChains()).rejects.toMatchObject({
      name: "ApiError",
      code: "network_error",
      status: 0,
    });
  });

  it("throws ContractError for a successful response with the wrong shape", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ chains: [] })));

    await expect(getChains()).rejects.toBeInstanceOf(ContractError);
  });

  it("encodes chain and date range in the same-origin history URL", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          generated_at: "2026-11-20T17:52:51.107921Z",
          analysis_only: true,
          chain: "btc",
          items: [],
        }),
      ),
    );

    await getScoreHistory("btc" satisfies ChainSlug, {
      from: "2026-10-21",
      to: "2026-11-19",
    });

    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/chains/btc/score-history?from=2026-10-21&to=2026-11-19",
      expect.any(Object),
    );
  });
});
