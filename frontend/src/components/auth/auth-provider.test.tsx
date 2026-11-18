import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./auth-provider";
import { setAccessToken } from "@/lib/api/client";

function Status() {
  const { status, user } = useAuth();
  return <p>{status === "authenticated" ? user?.email : status}</p>;
}

function RestoreSession() {
  const { status, user, restoreSession } = useAuth();
  return (
    <div>
      <p>{status === "authenticated" ? user?.email : status}</p>
      <button onClick={() => void restoreSession()}>restore session</button>
    </div>
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  setAccessToken(null);
  document.cookie = "chaincompass_csrf=; Max-Age=0; path=/";
  window.history.replaceState(null, "", "/en");
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

  it("leaves the OAuth callback refresh to the callback flow", async () => {
    document.cookie = "chaincompass_csrf=csrf-test; path=/";
    window.history.replaceState(null, "", "/en/auth/callback");
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
          email_verified: true,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <AuthProvider>
        <RestoreSession />
      </AuthProvider>,
    );

    await waitFor(() => expect(fetchMock).not.toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "restore session" }));
    expect(await screen.findByText("signed-in@example.com")).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.filter(
        ([input]) => String(input) === "/api/v1/auth/refresh",
      ),
    ).toHaveLength(1);
    window.history.replaceState(null, "", "/en");
  });
});
