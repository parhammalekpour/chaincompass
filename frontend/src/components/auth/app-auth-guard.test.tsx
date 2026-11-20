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

function abortablePendingFetch(
  _input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  return new Promise((_, reject) => {
    init?.signal?.addEventListener("abort", () => {
      reject(new DOMException("Aborted", "AbortError"));
    });
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
    vi.stubGlobal("fetch", vi.fn(abortablePendingFetch));
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
  });

  it("starts a new refresh attempt when Retry is selected", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn(abortablePendingFetch)
      .mockImplementationOnce(abortablePendingFetch)
      .mockImplementationOnce(abortablePendingFetch);
    vi.stubGlobal("fetch", fetchMock);
    renderGuard();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(INITIAL_SESSION_REFRESH_TIMEOUT_MS);
    });
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("status")).toBeInTheDocument();
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
    vi.stubGlobal("fetch", vi.fn(abortablePendingFetch));
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
  });
});
