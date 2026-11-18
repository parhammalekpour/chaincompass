import { StrictMode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import en from "../../../messages/en.json";
import fa from "../../../messages/fa.json";
import { ChangePasswordForm } from "./change-password-form";
import { ForgotPasswordForm } from "./forgot-password-form";
import { GoogleCallback } from "./google-callback";
import { LoginForm } from "./login-form";
import { ResendVerificationButton } from "./resend-verification-button";
import { ResetPasswordForm } from "./reset-password-form";
import { VerifyEmailPage } from "./verify-email-page";
import { setAccessToken } from "@/lib/api/client";

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  login: vi.fn(),
  refreshCurrentUser: vi.fn(),
  restoreSession: vi.fn(),
  status: "anonymous" as "anonymous" | "authenticated" | "loading",
  user: null as null | { email: string; email_verified: boolean },
}));

vi.mock("@/i18n/navigation", () => ({
  Link: ({
    href,
    children,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
  useRouter: () => ({ replace: mocks.replace }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace }),
}));

vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => ({
    status: mocks.status,
    user: mocks.user,
    login: mocks.login,
    refreshCurrentUser: mocks.refreshCurrentUser,
    restoreSession: mocks.restoreSession,
  }),
}));

function renderPage(
  children: React.ReactNode,
  locale: "en" | "fa" = "en",
) {
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={locale === "fa" ? fa : en}
    >
      {children}
    </NextIntlClientProvider>,
  );
}

function jsonResponse(body: unknown, status = 200, headers?: HeadersInit) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function setUrl(path: string) {
  window.history.replaceState(null, "", path);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  setAccessToken(null);
  document.cookie = "chaincompass_csrf=; Max-Age=0; path=/";
  mocks.replace.mockReset();
  mocks.login.mockReset();
  mocks.refreshCurrentUser.mockReset();
  mocks.restoreSession.mockReset();
  mocks.status = "anonymous";
  mocks.user = null;
  setUrl("/en");
});

describe("forgot password", () => {
  it.each([
    ["success response", jsonResponse({ message: "accepted" }, 202)],
    ["server error", jsonResponse({ error: { code: "internal_error", message: "hidden" } }, 500)],
  ])("shows the same neutral success screen after a %s", async (_label, response) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
    renderPage(<ForgotPasswordForm />);
    fireEvent.change(screen.getByLabelText(en.forgotPassword.email), {
      target: { value: "person@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: en.forgotPassword.submit }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      en.forgotPassword.successMessage,
    );
    expect(screen.queryByText("hidden")).not.toBeInTheDocument();
  });

  it.each([
    ["en", en, "Reset your password"],
    ["fa", fa, "بازنشانی گذرواژه"],
  ] as const)("renders in %s", async (locale, messages, title) => {
    renderPage(<ForgotPasswordForm />, locale);
    expect(await screen.findByRole("heading", { name: title })).toBeInTheDocument();
    expect(screen.getByLabelText(messages.forgotPassword.email)).toBeInTheDocument();
  });

  it("shows a countdown after a rate limit response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          { error: { code: "rate_limited", message: "hidden" } },
          429,
          { "Retry-After": "45" },
        ),
      ),
    );
    renderPage(<ForgotPasswordForm />);
    fireEvent.change(screen.getByLabelText(en.forgotPassword.email), {
      target: { value: "person@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: en.forgotPassword.submit }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      en.forgotPassword.successMessage,
    );
    expect(screen.getByText("Too many attempts. Try again in 45 seconds.")).toBeInTheDocument();
  });
});

describe("reset password", () => {
  it("does not submit when the token is missing", async () => {
    setUrl("/en/reset-password");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderPage(<ResetPasswordForm />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      en.authErrors.invalidResetToken,
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("submits a valid token after removing it from the address bar", async () => {
    setUrl("/en/reset-password?token=reset-secret-value");
    const fetchMock = vi.fn().mockImplementation(async (_input, init: RequestInit) => {
      expect(window.location.search).toBe("");
      expect(JSON.parse(String(init.body))).toMatchObject({
        token: "reset-secret-value",
        new_password: "a-different-strong-password",
      });
      return jsonResponse({ message: "changed" });
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage(<ResetPasswordForm />);
    fireEvent.change(await screen.findByLabelText(en.resetPassword.newPassword), {
      target: { value: "a-different-strong-password" },
    });
    fireEvent.change(screen.getByLabelText(en.resetPassword.confirmPassword), {
      target: { value: "a-different-strong-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: en.resetPassword.submit }));

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith(
      "/login?notice=password_reset",
    ));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(window.location.search).toBe("");
  });

  it("shows translated validation for mismatched passwords without a request", async () => {
    setUrl("/en/reset-password?token=present");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderPage(<ResetPasswordForm />);
    fireEvent.change(await screen.findByLabelText(en.resetPassword.newPassword), {
      target: { value: "strong-password-one" },
    });
    fireEvent.change(screen.getByLabelText(en.resetPassword.confirmPassword), {
      target: { value: "strong-password-two" },
    });
    fireEvent.click(screen.getByRole("button", { name: en.resetPassword.submit }));

    expect(await screen.findByText(en.authErrors.passwordMismatch)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows the invalid-link state for an expired token", async () => {
    setUrl("/en/reset-password?token=expired");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          { error: { code: "invalid_reset_token", message: "hidden" } },
          400,
        ),
      ),
    );
    renderPage(<ResetPasswordForm />);
    fireEvent.change(await screen.findByLabelText(en.resetPassword.newPassword), {
      target: { value: "a-different-strong-password" },
    });
    fireEvent.change(screen.getByLabelText(en.resetPassword.confirmPassword), {
      target: { value: "a-different-strong-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: en.resetPassword.submit }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      en.authErrors.invalidResetToken,
    );
  });
});

describe("verify email", () => {
  it("sends exactly one request under Strict Mode and removes the token", async () => {
    setUrl("/en/verify-email?token=verify-secret-value");
    let resolveResponse: ((response: Response) => void) | undefined;
    const fetchMock = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          resolveResponse = resolve;
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPage(
      <StrictMode>
        <VerifyEmailPage />
      </StrictMode>,
    );
    expect(screen.getByRole("status")).toHaveTextContent(en.verifyEmail.verifying);
    expect(window.location.search).toBe("");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    resolveResponse?.(jsonResponse({ message: "verified" }));
    expect(await screen.findByRole("heading", { name: en.verifyEmail.successTitle })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("shows invalid state for an expired verification token", async () => {
    setUrl("/en/verify-email?token=expired");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          { error: { code: "invalid_email_token", message: "hidden" } },
          400,
        ),
      ),
    );
    renderPage(<VerifyEmailPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      en.authErrors.invalidEmailToken,
    );
  });

  it("shows invalid state without a request when the token is missing", async () => {
    setUrl("/en/verify-email");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderPage(<VerifyEmailPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      en.authErrors.invalidEmailToken,
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refreshes the authenticated user after successful verification", async () => {
    mocks.status = "authenticated";
    mocks.user = { email: "person@example.com", email_verified: false };
    mocks.refreshCurrentUser.mockResolvedValue({
      email: "person@example.com",
      email_verified: true,
    });
    setUrl("/en/verify-email?token=verified");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ message: "verified" })),
    );
    renderPage(<VerifyEmailPage />);
    expect(
      await screen.findByRole("heading", { name: en.verifyEmail.successTitle }),
    ).toBeInTheDocument();
    await waitFor(() => expect(mocks.refreshCurrentUser).toHaveBeenCalledTimes(1));
  });
});

describe("Google callback", () => {
  it("restores the session once and redirects to the app", async () => {
    mocks.restoreSession.mockResolvedValue({});
    renderPage(
      <StrictMode>
        <GoogleCallback locale="en" />
      </StrictMode>,
    );
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/app"));
    expect(mocks.restoreSession).toHaveBeenCalledTimes(1);
  });

  it("redirects to login when refresh fails", async () => {
    mocks.restoreSession.mockRejectedValue(new Error("failure"));
    renderPage(<GoogleCallback locale="fa" />);
    await waitFor(() =>
      expect(mocks.replace).toHaveBeenCalledWith("/login?error=oauth_failed"),
    );
  });
});

describe("resend verification", () => {
  it("confirms a send and starts the 60-second cooldown", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, 202)));
    renderPage(<ResendVerificationButton email="person@example.com" />);
    fireEvent.click(screen.getByRole("button", { name: en.appShell.resendVerification }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      en.appShell.resendConfirmation,
    );
    expect(
      screen.getByRole("button", { name: "Try again in 60s" }),
    ).toBeDisabled();
  });

  it("uses Retry-After to set the 429 cooldown", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          { error: { code: "rate_limited", message: "hidden" } },
          429,
          { "Retry-After": "90" },
        ),
      ),
    );
    renderPage(<ResendVerificationButton email="person@example.com" />);
    fireEvent.click(screen.getByRole("button", { name: en.appShell.resendVerification }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Too many attempts. Try again in 90 seconds.",
    );
    expect(
      screen.getByRole("button", { name: "Try again in 90s" }),
    ).toBeDisabled();
  });
});

describe("change password", () => {
  it("submits successfully and shows a confirmation", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    renderPage(<ChangePasswordForm email="person@example.com" />);
    fireEvent.change(screen.getByLabelText(en.security.currentPassword), {
      target: { value: "current-password-value" },
    });
    fireEvent.change(screen.getByLabelText(en.security.newPassword), {
      target: { value: "new-password-value-123" },
    });
    fireEvent.change(screen.getByLabelText(en.security.confirmPassword), {
      target: { value: "new-password-value-123" },
    });
    fireEvent.click(screen.getByRole("button", { name: en.security.submit }));
    expect(await screen.findByRole("status")).toHaveTextContent(en.security.success);
  });

  it("shows an invalid current password beside that field", async () => {
    document.cookie = "chaincompass_csrf=csrf-test; path=/";
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) =>
        String(input) === "/api/v1/auth/refresh"
          ? jsonResponse(
              {
                access_token: "test-access",
                token_type: "bearer",
                expires_in: 900,
                user: {
                  id: "user-1",
                  email: "person@example.com",
                  locale: "en",
                  role: "user",
                },
              },
            )
          : jsonResponse(
              { error: { code: "invalid_credentials", message: "hidden" } },
              401,
            ),
      ),
    );
    renderPage(<ChangePasswordForm email="person@example.com" />);
    fireEvent.change(screen.getByLabelText(en.security.currentPassword), {
      target: { value: "wrong-current-password" },
    });
    fireEvent.change(screen.getByLabelText(en.security.newPassword), {
      target: { value: "new-password-value-123" },
    });
    fireEvent.change(screen.getByLabelText(en.security.confirmPassword), {
      target: { value: "new-password-value-123" },
    });
    fireEvent.click(screen.getByRole("button", { name: en.security.submit }));
    expect(await screen.findByText(en.authErrors.currentPasswordInvalid)).toBeInTheDocument();
    expect(screen.getByLabelText(en.security.currentPassword)).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });
});

describe("login query notices", () => {
  beforeEach(() => {
    mocks.login.mockResolvedValue(undefined);
  });

  it.each([
    ["error=oauth_failed", en.login.oauthFailedNotice],
    ["notice=password_reset", en.login.passwordResetNotice],
  ])("renders a whitelisted notice for %s", async (query, expected) => {
    setUrl(`/en/login?${query}`);
    renderPage(<LoginForm locale="en" />);
    expect(await screen.findByText(expected)).toBeInTheDocument();
  });

  it("ignores unknown query values rather than rendering them", async () => {
    setUrl("/en/login?error=secret-error-value&notice=secret-notice-value");
    renderPage(<LoginForm locale="en" />);
    expect(await screen.findByRole("heading", { name: en.login.title })).toBeInTheDocument();
    expect(screen.queryByText("secret-error-value")).not.toBeInTheDocument();
    expect(screen.queryByText("secret-notice-value")).not.toBeInTheDocument();
  });
});
