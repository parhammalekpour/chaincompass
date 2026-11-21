import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import en from "../../../messages/en.json";
import fa from "../../../messages/fa.json";
import {
  AuthProvider,
  INITIAL_SESSION_REFRESH_TIMEOUT_MS,
} from "./auth-provider";
import { AppAuthGuard } from "./app-auth-guard";

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

function renderGuard(locale: "en" | "fa" = "en") {
  const messages = locale === "fa" ? fa : en;
  return render(
    <NextIntlClientProvider locale={locale} messages={messages}>
      <AuthProvider>
        <AppAuthGuard locale={locale}>
          <p>Protected content</p>
        </AppAuthGuard>
      </AuthProvider>
    </NextIntlClientProvider>,
  );
}

function delayedFailingFetch(): Promise<Response> {
  return new Promise((_, reject) => {
    setTimeout(
      () => reject(new TypeError("offline")),
      2 * INITIAL_SESSION_REFRESH_TIMEOUT_MS,
    );
  });
}

function expiredRefreshResponse() {
  return new Response(
    JSON.stringify({
      error: { code: "invalid_refresh_token", message: "Invalid refresh" },
    }),
    { status: 401, headers: { "Content-Type": "application/json" } },
  );
}

function successfulRefreshResponse() {
  return new Response(
    JSON.stringify({
      access_token: "memory-only",
      token_type: "bearer",
      expires_in: 900,
      user: {
        id: "user-1",
        email: "signed-in@example.com",
        locale: "en",
        role: "user",
      },
    }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
}

beforeEach(() => {
  replace.mockReset();
  document.cookie = "chaincompass_csrf=csrf-test; path=/";
  window.history.replaceState(null, "", "/en/app/chains/btc?view=score");
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  document.cookie = "chaincompass_csrf=; Max-Age=0; path=/";
  window.history.replaceState(null, "", "/en");
});

describe("AppAuthGuard refresh recovery", () => {
  it("shows a retryable error when the initial refresh times out", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn(delayedFailingFetch));
    renderGuard();

    expect(screen.getByRole("status")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(INITIAL_SESSION_REFRESH_TIMEOUT_MS);
    });

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Your session could not be restored",
    );
    expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
    expect(replace).not.toHaveBeenCalled();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(INITIAL_SESSION_REFRESH_TIMEOUT_MS);
    });
  });

  it("shares a timed-out refresh until it settles, then retries once", async () => {
    vi.useFakeTimers();
    let rejectFirst: ((error: Error) => void) | undefined;
    let refreshCalls = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path === "/api/v1/auth/refresh") {
        refreshCalls += 1;
        if (refreshCalls === 1) {
          return new Promise<Response>((_resolve, reject) => {
            rejectFirst = reject;
          });
        }
        return Promise.resolve(successfulRefreshResponse());
      }
      if (path === "/api/v1/auth/me") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              id: "user-1",
              email: "signed-in@example.com",
              locale: "en",
              role: "user",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return Promise.reject(new Error("Unexpected request"));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderGuard();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(INITIAL_SESSION_REFRESH_TIMEOUT_MS);
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    });
    expect(refreshCalls).toBe(1);

    await act(async () => {
      rejectFirst?.(new TypeError("offline"));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Your session could not be restored",
    );

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Try again" }));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText("Protected content")).toBeInTheDocument();
    expect(refreshCalls).toBe(2);
  });

  it("redirects to login when refresh returns 401", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(expiredRefreshResponse()));
    renderGuard();

    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith(
        "/en/login?next=%2Fen%2Fapp%2Fchains%2Fbtc%3Fview%3Dscore",
      );
    });
  });

  it("shows a Persian retry message", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn(delayedFailingFetch));
    renderGuard("fa");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(INITIAL_SESSION_REFRESH_TIMEOUT_MS);
    });

    expect(screen.getByRole("alert")).toHaveTextContent(
      "بازیابی نشست انجام نشد",
    );
    expect(
      screen.getByRole("button", { name: "تلاش دوباره" }),
    ).toBeVisible();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(INITIAL_SESSION_REFRESH_TIMEOUT_MS);
    });
  });
});
