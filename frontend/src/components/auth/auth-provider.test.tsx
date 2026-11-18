import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./auth-provider";

function Status() {
  const { status, user } = useAuth();
  return <p>{status === "authenticated" ? user?.email : status}</p>;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  document.cookie = "chaincompass_csrf=; Max-Age=0; path=/";
});

describe("AuthProvider bootstrap", () => {
  it("goes anonymous without a CSRF cookie and makes no request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(
      <AuthProvider>
        <Status />
      </AuthProvider>,
    );

    expect(await screen.findByText("anonymous")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refreshes and loads the current user when a CSRF cookie exists", async () => {
    document.cookie = "chaincompass_csrf=csrf-test; path=/";
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/v1/auth/refresh") {
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
      return new Response(
        JSON.stringify({
          id: "user-1",
          email: "signed-in@example.com",
          locale: "en",
          role: "user",
          email_verified: false,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <AuthProvider>
        <Status />
      </AuthProvider>,
    );

    expect(await screen.findByText("signed-in@example.com")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });

  it("goes anonymous when a refresh attempt fails", async () => {
    document.cookie = "chaincompass_csrf=csrf-test; path=/";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "invalid_refresh_token", message: "hidden" },
        }),
        { status: 401, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <AuthProvider>
        <Status />
      </AuthProvider>,
    );

    expect(await screen.findByText("anonymous")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
