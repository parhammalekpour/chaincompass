import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";
import en from "../../../messages/en.json";
import fa from "../../../messages/fa.json";
import { AuthProvider } from "./auth-provider";
import { LoginForm } from "./login-form";
import { RegisterForm } from "./register-form";

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
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  document.cookie = "chaincompass_csrf=; Max-Age=0; path=/";
});

function renderWithMessages(
  children: React.ReactNode,
  locale: "en" | "fa",
) {
  return render(
    <NextIntlClientProvider locale={locale} messages={locale === "fa" ? fa : en}>
      <AuthProvider>{children}</AuthProvider>
    </NextIntlClientProvider>,
  );
}

describe("login form", () => {
  it.each([
    ["en", en, "Enter a valid email address."],
    ["fa", fa, "نشانی ایمیل معتبر وارد کنید."],
  ] as const)("shows translated validation errors in %s", async (locale, messages, emailError) => {
    renderWithMessages(
      <LoginForm locale={locale} />,
      locale,
    );
    await screen.findByRole("heading", { name: messages.login.title });
    fireEvent.click(screen.getByRole("button", { name: messages.login.submit }));
    expect(await screen.findByText(emailError)).toBeInTheDocument();
    expect(
      screen.getByText(messages.authErrors.passwordRequired),
    ).toBeInTheDocument();
  });

  it("shows a translated invalid-credentials message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: { code: "invalid_credentials", message: "do not show this" },
          }),
          { status: 401, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    renderWithMessages(<LoginForm locale="en" />, "en");
    fireEvent.change(screen.getByLabelText(en.login.email), {
      target: { value: "person@example.com" },
    });
    fireEvent.change(screen.getByLabelText(en.login.password), {
      target: { value: "valid-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: en.login.submit }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      en.authErrors.invalidCredentials,
    );
    expect(screen.queryByText("do not show this")).not.toBeInTheDocument();
  });

  it("shows a disabled loading submit state while the request is pending", async () => {
    let resolveRequest: ((response: Response) => void) | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            resolveRequest = resolve;
          }),
      ),
    );
    renderWithMessages(<LoginForm locale="en" />, "en");
    fireEvent.change(screen.getByLabelText(en.login.email), {
      target: { value: "person@example.com" },
    });
    fireEvent.change(screen.getByLabelText(en.login.password), {
      target: { value: "valid-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: en.login.submit }));

    const submit = await screen.findByRole("button", {
      name: en.login.submitting,
    });
    expect(submit).toBeDisabled();
    resolveRequest?.(
      new Response(
        JSON.stringify({
          error: { code: "invalid_credentials", message: "hidden" },
        }),
        { status: 401, headers: { "Content-Type": "application/json" } },
      ),
    );
    await waitFor(() => expect(submit).toBeEnabled());
  });
});

describe("register form", () => {
  it.each([
    { message: "new account accepted" },
    { message: "duplicate account accepted" },
  ])("shows the same neutral success message regardless of server detail", async (body) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(body), {
          status: 202,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    renderWithMessages(<RegisterForm locale="en" />, "en");
    fireEvent.change(screen.getByLabelText(en.register.email), {
      target: { value: "person@example.com" },
    });
    fireEvent.change(screen.getByLabelText(en.register.password), {
      target: { value: "Valid-Register-Password-61!" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: en.register.submit }),
    );

    expect(await screen.findByRole("status")).toHaveTextContent(
      en.register.successMessage,
    );
    expect(screen.queryByText(body.message)).not.toBeInTheDocument();
  });
});
