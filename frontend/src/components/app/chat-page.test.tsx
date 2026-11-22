import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import en from "../../../messages/en.json";
import fa from "../../../messages/fa.json";
import { ApiError } from "@/lib/api/client";
import type { AgentSseEvent } from "@/lib/agent/contracts";
import { ChatPage, isConversationId } from "./chat-page";

const mocks = vi.hoisted(() => {
  const state = {
    query: "",
    router: { replace: vi.fn() },
    listConversations: vi.fn(),
    createConversation: vi.fn(),
    getConversation: vi.fn(),
    deleteConversation: vi.fn(),
    sendMessage: vi.fn(),
    pathname: "/app/chat",
  };
  const searchParams = {
    get: (name: string) => new URLSearchParams(state.query).get(name),
    has: (name: string) => new URLSearchParams(state.query).has(name),
    toString: () => state.query,
  };
  return Object.assign(state, { searchParams });
});

vi.mock("next/navigation", () => ({
  useSearchParams: () => mocks.searchParams,
}));

vi.mock("@/i18n/navigation", () => ({
  Link: ({
    href,
    children,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & {
    href: string;
    children: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
  usePathname: () => mocks.pathname,
  useRouter: () => mocks.router,
}));

vi.mock("@/lib/agent/client", () => ({
  listConversations: mocks.listConversations,
  createConversation: mocks.createConversation,
  getConversation: mocks.getConversation,
  deleteConversation: mocks.deleteConversation,
  sendMessage: mocks.sendMessage,
}));

const conversationId = "a39b68f7-63a1-4f4f-9f7a-8bb1f83e38e1";
const conversation = {
  id: conversationId,
  title: "Test conversation",
  created_at: "2026-11-20T12:00:00Z",
  updated_at: "2026-11-20T12:00:00Z",
};

function chatTree(locale: "en" | "fa" = "en") {
  return (
    <NextIntlClientProvider
      locale={locale}
      messages={locale === "fa" ? fa : en}
    >
      <ChatPage />
    </NextIntlClientProvider>
  );
}

function renderChat(locale: "en" | "fa" = "en", search = `c=${conversationId}`) {
  mocks.query = search;
  return render(chatTree(locale));
}

function event(type: AgentSseEvent["type"], data: unknown): AgentSseEvent {
  return { type, data } as AgentSseEvent;
}

function stream(events: AgentSseEvent[]) {
  return async function* () {
    for (const item of events) yield item;
  };
}

function setupApi() {
  mocks.listConversations.mockResolvedValue({ conversations: [conversation] });
  mocks.getConversation.mockResolvedValue({ ...conversation, messages: [] });
  mocks.createConversation.mockResolvedValue(conversation);
  mocks.deleteConversation.mockResolvedValue(undefined);
  mocks.sendMessage.mockImplementation(stream([]));
}

beforeEach(() => {
  mocks.query = "";
  mocks.router.replace.mockReset();
  mocks.listConversations.mockReset();
  mocks.createConversation.mockReset();
  mocks.getConversation.mockReset();
  mocks.deleteConversation.mockReset();
  mocks.sendMessage.mockReset();
  setupApi();
  let id = 0;
  vi.stubGlobal("crypto", {
    randomUUID: () => `00000000-0000-4000-8000-${String(++id).padStart(12, "0")}`,
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ChatPage", () => {
  it("accepts only UUID conversation query values", () => {
    expect(isConversationId(conversationId)).toBe(true);
    expect(isConversationId("not-a-uuid")).toBe(false);

    renderChat("en", "c=not-a-uuid");

    expect(mocks.router.replace).toHaveBeenCalledWith("/app/chat", {
      scroll: false,
    });
  });

  it("shows user text, tool activity, and the streamed answer as plain text", async () => {
    mocks.sendMessage.mockImplementation(
      stream([
        event("tool_call", {
          name: "get_chain_snapshot",
          args: { slug: "btc" },
        }),
        event("tool_result", {
          name: "get_chain_snapshot",
          ok: true,
          summary: "<img onerror=alert(1)>",
        }),
        event("token", {
          text: '<img onerror="alert(1)"><a href="javascript:alert(1)">answer</a>',
        }),
        event("final", {
          grounding_status: "ok",
          refusal: false,
          tool_names: ["get_chain_snapshot"],
        }),
        event("done", {}),
      ]),
    );
    renderChat();
    const composer = screen.getByRole("textbox", { name: "Your message" });
    await screen.findByText("Test conversation");
    expect(screen.queryByText("Loading conversations")).not.toBeInTheDocument();
    fireEvent.change(composer, { target: { value: "Show the snapshot" } });
    fireEvent.keyDown(composer, { key: "Enter" });

    expect(await screen.findByText("Show the snapshot")).toBeVisible();
    expect(await screen.findByText("Retrieved: chain snapshot")).toBeVisible();
    expect(
      await screen.findByText(
        '<img onerror="alert(1)"><a href="javascript:alert(1)">answer</a>',
      ),
    ).toBeVisible();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "answer" })).not.toBeInTheDocument();
  });

  it("shows live tool chips before the answer and preserves fallback newlines", async () => {
    let releaseToolResult: (() => void) | undefined;
    let releaseAnswer: (() => void) | undefined;
    const toolResultGate = new Promise<void>((resolve) => {
      releaseToolResult = resolve;
    });
    const answerGate = new Promise<void>((resolve) => {
      releaseAnswer = resolve;
    });
    mocks.sendMessage.mockImplementation(
      async function* () {
        yield event("tool_call", {
          name: "get_chain_snapshot",
          args: { slug: "btc" },
        });
        await toolResultGate;
        yield event("tool_result", {
          name: "get_chain_snapshot",
          ok: true,
          summary: "data_returned",
        });
        await answerGate;
        yield event("token", { text: "First line\nSecond line" });
        yield event("final", {
          grounding_status: "ok",
          refusal: false,
          tool_names: ["get_chain_snapshot"],
        });
        yield event("done", {});
      },
    );
    const { container } = renderChat();
    const composer = screen.getByRole("textbox", { name: "Your message" });
    await screen.findByText("Test conversation");
    fireEvent.change(composer, { target: { value: "Show the snapshot" } });
    fireEvent.keyDown(composer, { key: "Enter" });

    const runningChip = await screen.findByText("Looking up: chain snapshot");
    const assistant = screen.getByText("Assistant").closest("article");
    expect(assistant).not.toBeNull();
    expect(runningChip).toBeVisible();
    expect(assistant?.querySelector("svg.animate-spin")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Checking data...");
    expect(screen.queryByText("First line\nSecond line")).not.toBeInTheDocument();
    expect(assistant?.children[1]).toContainElement(runningChip);

    await act(async () => {
      releaseToolResult?.();
    });
    const completedChip = await screen.findByText("Retrieved: chain snapshot");
    expect(completedChip).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Checking data...");
    expect(screen.queryByText("First line\nSecond line")).not.toBeInTheDocument();

    await act(async () => {
      releaseAnswer?.();
    });
    await waitFor(() =>
      expect(
        assistant?.querySelector("p.whitespace-pre-wrap")?.textContent,
      ).toBe("First line\nSecond line"),
    );
    const answer = assistant?.querySelector("p.whitespace-pre-wrap");
    expect(answer).not.toBeNull();
    expect(answer).toHaveClass("whitespace-pre-wrap");
    expect(assistant?.children[1]).toContainElement(completedChip);
    expect(assistant?.children[2]).toBe(answer);
    expect(
      await screen.findByText("Response complete.", {
        selector: '[aria-live="polite"]',
      }),
    ).toBeVisible();
    expect(container.querySelectorAll('[aria-live="polite"]')).toHaveLength(1);
  });

  it("marks an unsuccessful tool result as unavailable", async () => {
    mocks.sendMessage.mockImplementation(
      stream([
        event("tool_call", {
          name: "get_chain_snapshot",
          args: { slug: "btc" },
        }),
        event("tool_result", {
          name: "get_chain_snapshot",
          ok: false,
          summary: "data_unavailable",
        }),
        event("final", {
          grounding_status: "failed",
          refusal: false,
          tool_names: ["get_chain_snapshot"],
        }),
        event("done", {}),
      ]),
    );
    renderChat();
    const composer = screen.getByRole("textbox", { name: "Your message" });
    await screen.findByText("Test conversation");
    fireEvent.change(composer, { target: { value: "Show the snapshot" } });
    fireEvent.keyDown(composer, { key: "Enter" });

    expect(await screen.findByText("Unavailable: chain snapshot")).toBeVisible();
    expect(screen.getByText(/only retrieved data is shown/)).toBeVisible();
  });

  it.each([
    ["retried", "Answer was re-checked against the data."],
    [
      "failed",
      "This answer could not be verified, so only retrieved data is shown.",
    ],
    ["refused", "Historical analysis only"],
  ] as const)("shows the %s status notice", async (status, notice) => {
    mocks.sendMessage.mockImplementation(
      stream([
        event("final", {
          grounding_status: status,
          refusal: status === "refused",
          tool_names: [],
        }),
        event("done", {}),
      ]),
    );
    renderChat();
    const composer = screen.getByRole("textbox", { name: "Your message" });
    await screen.findByText("Test conversation");
    fireEvent.change(composer, { target: { value: "Explain the data" } });
    fireEvent.keyDown(composer, { key: "Enter" });

    expect(await screen.findByText(notice)).toBeVisible();
  });

  it("aborts a running request when Stop is pressed", async () => {
    let activeSignal: AbortSignal | undefined;
    mocks.sendMessage.mockImplementation(
      async function* (_id: string, _content: string, signal: AbortSignal) {
        activeSignal = signal;
        yield event("tool_call", {
          name: "get_chain_snapshot",
          args: { slug: "btc" },
        });
        await new Promise<void>((resolve) =>
          signal.addEventListener("abort", () => resolve(), { once: true }),
        );
      },
    );
    renderChat();
    const composer = screen.getByRole("textbox", { name: "Your message" });
    await screen.findByText("Test conversation");
    fireEvent.change(composer, { target: { value: "Inspect BTC" } });
    fireEvent.keyDown(composer, { key: "Enter" });
    fireEvent.keyDown(composer, { key: "Enter" });

    fireEvent.click(await screen.findByRole("button", { name: "Stop" }));
    await waitFor(() => expect(activeSignal?.aborted).toBe(true));
    expect(mocks.sendMessage).toHaveBeenCalledTimes(1);
  });

  it("shows provider setup and rate-limit errors", async () => {
    mocks.sendMessage.mockImplementationOnce(async function* () {
      throw new ApiError("llm_not_configured", 503);
    });
    const first = renderChat();
    await screen.findByText("Test conversation");
    fireEvent.change(screen.getByRole("textbox", { name: "Your message" }), {
      target: { value: "Explain the data" },
    });
    fireEvent.keyDown(screen.getByRole("textbox", { name: "Your message" }), {
      key: "Enter",
    });
    expect(
      await screen.findByText("The assistant is not configured on this server"),
    ).toBeVisible();
    first.unmount();

    mocks.sendMessage.mockImplementationOnce(async function* () {
      throw new ApiError("rate_limited", 429, 45);
    });
    renderChat();
    await screen.findByText("Test conversation");
    fireEvent.change(screen.getByRole("textbox", { name: "Your message" }), {
      target: { value: "Explain the data" },
    });
    fireEvent.keyDown(screen.getByRole("textbox", { name: "Your message" }), {
      key: "Enter",
    });
    expect(await screen.findByText("Too many requests. Try again in 45 seconds.")).toBeVisible();
  });

  it("caps composer input, skips empty sends, and renders Persian layout with Latin counts", async () => {
    const { container } = renderChat("fa", "");
    const composer = screen.getByRole("textbox", { name: "پیام شما" });
    expect(container.querySelector("main")).toHaveAttribute("dir", "rtl");
    expect(composer).toHaveAttribute("dir", "auto");
    expect(screen.getByText("0 / 2,000")).toHaveAttribute("dir", "ltr");
    expect(screen.getByRole("button", { name: "ارسال" })).toBeDisabled();
    fireEvent.change(composer, { target: { value: "x".repeat(2001) } });
    expect(composer).toHaveValue("x".repeat(2000));
    expect(screen.getByText("2,000 / 2,000")).toBeVisible();
    expect(mocks.sendMessage).not.toHaveBeenCalled();
  });

  it("places starter questions in the composer without sending them", async () => {
    renderChat("en", "");
    const composer = screen.getByRole("textbox", { name: "Your message" });
    const starter =
      "Summarise the current health score and confidence for each chain.";

    fireEvent.click(await screen.findByRole("button", { name: starter }));

    expect(composer).toHaveValue(starter);
    expect(mocks.sendMessage).not.toHaveBeenCalled();
  });

  it.each([
    [
      "en",
      `ask=report&chain=eth`,
      en.chatPage.reportQuestion.replace(
        "{chainName}",
        en.dashboard.chainNames.eth,
      ),
    ],
    [
      "fa",
      `ask=report&chain=eth`,
      fa.chatPage.reportQuestion.replace(
        "{chainName}",
        fa.dashboard.chainNames.eth,
      ),
    ],
  ] as const)(
    "prefills the fixed %s question, focuses it, and does not send or create",
    async (locale, search, question) => {
      renderChat(locale, search);
      const composer = screen.getByRole("textbox", {
        name: locale === "fa" ? "پیام شما" : "Your message",
      });

      await waitFor(() => expect(composer).toHaveValue(question));
      expect(composer).toHaveFocus();
      expect(mocks.router.replace).toHaveBeenCalledWith("/app/chat", {
        scroll: false,
      });
      expect(mocks.sendMessage).not.toHaveBeenCalled();
      expect(mocks.createConversation).not.toHaveBeenCalled();
      expect(mocks.getConversation).not.toHaveBeenCalled();
    },
  );

  it("ignores an unknown chain in the report prefill", async () => {
    renderChat("en", "ask=report&chain=unknown");
    const composer = screen.getByRole("textbox", { name: "Your message" });
    await screen.findByText("Start with public data");

    expect(composer).toHaveValue("");
    expect(mocks.router.replace).not.toHaveBeenCalled();
    expect(mocks.sendMessage).not.toHaveBeenCalled();
    expect(mocks.createConversation).not.toHaveBeenCalled();
  });

  it("ignores an unknown ask and unrelated URL text", async () => {
    renderChat("en", "ask=summary&chain=eth&text=URL%20text");
    const composer = screen.getByRole("textbox", { name: "Your message" });
    await screen.findByText("Start with public data");

    expect(composer).toHaveValue("");
    expect(mocks.router.replace).not.toHaveBeenCalled();
    expect(mocks.sendMessage).not.toHaveBeenCalled();
    expect(mocks.createConversation).not.toHaveBeenCalled();
  });

  it("does not override an existing conversation view", async () => {
    renderChat(
      "en",
      `c=${conversationId}&ask=report&chain=eth`,
    );
    const composer = screen.getByRole("textbox", { name: "Your message" });

    await screen.findByText("Test conversation");
    expect(composer).toHaveValue("");
    expect(mocks.getConversation).toHaveBeenCalledWith(conversationId);
    expect(mocks.router.replace).not.toHaveBeenCalled();
    expect(mocks.sendMessage).not.toHaveBeenCalled();
    expect(mocks.createConversation).not.toHaveBeenCalled();
  });

  it("preserves existing user text and ignores extra URL text", async () => {
    const view = renderChat("en", "");
    const composer = screen.getByRole("textbox", { name: "Your message" });
    fireEvent.change(composer, { target: { value: "My existing draft" } });

    mocks.query = "ask=report&chain=eth&text=URL%20text";
    view.rerender(chatTree("en"));

    expect(composer).toHaveValue("My existing draft");
    expect(mocks.router.replace).toHaveBeenCalledWith(
      "/app/chat?text=URL+text",
      { scroll: false },
    );
    expect(mocks.sendMessage).not.toHaveBeenCalled();
    expect(mocks.createConversation).not.toHaveBeenCalled();
  });

  it("returns to the conversation list when the selected conversation is missing", async () => {
    mocks.getConversation.mockRejectedValue(
      new ApiError("conversation_not_found", 404),
    );
    renderChat();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This conversation is no longer available.",
    );
    expect(mocks.router.replace).toHaveBeenCalledWith("/app/chat", {
      scroll: false,
    });
  });

  it("aborts a pending request when unmounted", async () => {
    let activeSignal: AbortSignal | undefined;
    mocks.sendMessage.mockImplementation(
      async function* (_id: string, _content: string, signal: AbortSignal) {
        activeSignal = signal;
        await new Promise<void>((resolve) =>
          signal.addEventListener("abort", () => resolve(), { once: true }),
        );
      },
    );
    const view = renderChat();
    const composer = screen.getByRole("textbox", { name: "Your message" });
    await screen.findByText("Test conversation");
    fireEvent.change(composer, { target: { value: "Inspect BTC" } });
    fireEvent.keyDown(composer, { key: "Enter" });
    await waitFor(() => expect(activeSignal).toBeDefined());

    view.unmount();
    expect(activeSignal?.aborted).toBe(true);
  });
});
