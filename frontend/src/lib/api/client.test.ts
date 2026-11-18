import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  apiRequest,
  NetworkError,
  setAccessToken,
} from "./client";

const authResponse = {
  access_token: "in-memory-test-access",
  token_type: "bearer",
  expires_in: 900,
  user: {
    id: "user-1",
    email: "person@example.com",
    locale: "en",
    role: "user",
  },
};

function jsonResponse(body: unknown, status = 200, headers?: HeadersInit) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  setAccessToken(null);
  document.cookie = "chaincompass_csrf=; Max-Age=0; path=/";
});

describe("apiRequest", () => {
  it("parses structured backend errors without exposing raw message text", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          { error: { code: "invalid_credentials", message: "private detail" } },
          401,
        ),
      ),
    );
    await expect(
      apiRequest("/api/v1/auth/login", { authRetry: false }),
    ).rejects.toMatchObject({
      name: "ApiError",
      code: "invalid_credentials",
      status: 401,
    });
  });

  it("exposes 429 Retry-After seconds", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          { error: { code: "rate_limited", message: "hidden" } },
          429,
          { "Retry-After": "17" },
        ),
      ),
    );
    await expect(apiRequest("/api/v1/auth/login")).rejects.toMatchObject({
      code: "rate_limited",
      status: 429,
      retryAfterSeconds: 17,
    });
  });

  it("handles 204 and non-JSON responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(new Response(null, { status: 204 }))
        .mockResolvedValueOnce(new Response("not json", { status: 502 })),
    );
    await expect(apiRequest<void>("/api/v1/auth/logout")).resolves.toBeUndefined();
    await expect(apiRequest("/api/v1/auth/me")).rejects.toMatchObject({
      code: "http_error",
      status: 502,
    });
  });

  it("sends the in-memory bearer token and JSON request body same-origin", async () => {
    setAccessToken("memory-access");
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ accepted: true }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      apiRequest("/api/v1/auth/example", {
        method: "POST",
        body: { value: "sample" },
      }),
    ).resolves.toEqual({ accepted: true });
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(request.credentials).toBe("same-origin");
    expect(new Headers(request.headers).get("Authorization")).toBe(
      "Bearer memory-access",
    );
    expect(new Headers(request.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(request.body).toBe(JSON.stringify({ value: "sample" }));
  });

  it("wraps network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await expect(apiRequest("/api/v1/auth/me")).rejects.toBeInstanceOf(
      NetworkError,
    );
  });

  it("shares one refresh among three concurrent unauthorized requests", async () => {
    document.cookie = "chaincompass_csrf=csrf-test; path=/";
    const calls = new Map<string, number>();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      calls.set(path, (calls.get(path) ?? 0) + 1);
      if (path === "/api/v1/auth/refresh") return jsonResponse(authResponse);
      if (calls.get(path) === 1) {
        return jsonResponse(
          { error: { code: "invalid_access_token", message: "hidden" } },
          401,
        );
      }
      return jsonResponse({ path });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      Promise.all([
        apiRequest("/api/v1/auth/a"),
        apiRequest("/api/v1/auth/b"),
        apiRequest("/api/v1/auth/c"),
      ]),
    ).resolves.toHaveLength(3);

    expect(calls.get("/api/v1/auth/refresh")).toBe(1);
    expect(calls.get("/api/v1/auth/a")).toBe(2);
    expect(calls.get("/api/v1/auth/b")).toBe(2);
    expect(calls.get("/api/v1/auth/c")).toBe(2);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/refresh",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRF-Token": "csrf-test" },
      }),
    );
  });

  it("reuses a newly refreshed token for a late concurrent 401", async () => {
    document.cookie = "chaincompass_csrf=csrf-test; path=/";
    let resolveSlow: ((response: Response) => void) | undefined;
    let refreshCalls = 0;
    let slowCalls = 0;
    let fastCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const path = String(input);
        if (path === "/api/v1/auth/slow") {
          slowCalls += 1;
          if (slowCalls === 1) {
            return new Promise<Response>((resolve) => {
              resolveSlow = resolve;
            });
          }
          return Promise.resolve(jsonResponse({ ok: true }));
        }
        if (path === "/api/v1/auth/refresh") {
          refreshCalls += 1;
          return Promise.resolve(jsonResponse(authResponse));
        }
        if (path === "/api/v1/auth/fast") {
          fastCalls += 1;
          if (fastCalls > 1) return Promise.resolve(jsonResponse({ ok: true }));
          return Promise.resolve(
            jsonResponse(
              { error: { code: "invalid_access_token", message: "hidden" } },
              401,
            ),
          );
        }
        return Promise.resolve(jsonResponse({ ok: true }));
      }),
    );

    const slowRequest = apiRequest("/api/v1/auth/slow");
    const fastRequest = apiRequest("/api/v1/auth/fast");
    await expect(fastRequest).resolves.toEqual({ ok: true });
    resolveSlow?.(
      jsonResponse(
        { error: { code: "invalid_access_token", message: "hidden" } },
        401,
      ),
    );
    await expect(slowRequest).resolves.toEqual({ ok: true });
    expect(refreshCalls).toBe(1);
  });

  it("retries the original request once and does not loop on a second 401", async () => {
    document.cookie = "chaincompass_csrf=csrf-test; path=/";
    let originalCalls = 0;
    let refreshCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/api/v1/auth/refresh") {
          refreshCalls += 1;
          return jsonResponse(authResponse);
        }
        originalCalls += 1;
        return jsonResponse(
          { error: { code: "invalid_access_token", message: "hidden" } },
          401,
        );
      }),
    );

    await expect(apiRequest("/api/v1/auth/me")).rejects.toBeInstanceOf(ApiError);
    expect(originalCalls).toBe(2);
    expect(refreshCalls).toBe(1);
  });

  it("clears the in-memory token when refresh fails", async () => {
    document.cookie = "chaincompass_csrf=csrf-test; path=/";
    setAccessToken("old-access-token");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          { error: { code: "invalid_access_token", message: "hidden" } },
          401,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          { error: { code: "invalid_refresh_token", message: "hidden" } },
          401,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest("/api/v1/auth/me")).rejects.toMatchObject({
      code: "invalid_refresh_token",
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
