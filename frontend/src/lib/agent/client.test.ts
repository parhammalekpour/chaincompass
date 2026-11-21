import { afterEach, describe, expect, it, vi } from "vitest";
import conversationFixture from "@/test/fixtures/agent-conversation.json";
import conversationsFixture from "@/test/fixtures/agent-conversations.json";
import {
  conversationDetailSchema,
  conversationListSchema,
} from "./contracts";
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  sendMessage,
} from "./client";
import {
  setAccessToken,
  subscribeToSessionInvalidation,
} from "@/lib/api/client";
import type { AgentSseEvent } from "./contracts";

const authResponse = {
  access_token: "refreshed-access",
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

function eventStream(events: AgentSseEvent[]) {
  const encoder = new TextEncoder();
  const chunks = events.map(
    ({ type, data }) =>
      encoder.encode(`event: ${type}\ndata: ${JSON.stringify(data)}\n\n`),
  );
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(chunk);
        controller.close();
      },
    }),
    { status: 200, headers: { "Content-Type": "text/event-stream" } },
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  setAccessToken(null);
  document.cookie = "chaincompass_csrf=; Max-Age=0; path=/";
});

describe("agent contracts and client", () => {
  it("validates backend-shaped conversation fixtures", () => {
    expect(conversationListSchema.parse(conversationsFixture)).toEqual(
      conversationsFixture,
    );
    expect(conversationDetailSchema.parse(conversationFixture)).toEqual(
      conversationFixture,
    );
  });

  it("uses the authenticated API conventions for conversation operations", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(conversationsFixture))
      .mockResolvedValueOnce(jsonResponse(conversationsFixture.conversations[0]))
      .mockResolvedValueOnce(jsonResponse(conversationFixture))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    setAccessToken("memory-access");
    vi.stubGlobal("fetch", fetchMock);

    await expect(listConversations()).resolves.toEqual(conversationsFixture);
    await expect(createConversation()).resolves.toEqual(
      conversationsFixture.conversations[0],
    );
    await expect(
      getConversation(conversationsFixture.conversations[0].id),
    ).resolves.toEqual(conversationFixture);
    await expect(
      deleteConversation(conversationsFixture.conversations[0].id),
    ).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/agent/conversations",
      expect.objectContaining({ credentials: "same-origin" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/agent/conversations",
      expect.objectContaining({
        method: "POST",
        body: "{}",
        credentials: "same-origin",
      }),
    );
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(request.headers).get("Authorization")).toBe(
      "Bearer memory-access",
    );
  });

  it("posts a message and returns parsed events from the response stream", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      eventStream([
        {
          type: "meta",
          data: {
            user_message_id: "22000000-0000-4000-8000-000000000003",
            assistant_message_id: "22000000-0000-4000-8000-000000000004",
            language: "en",
          },
        },
        { type: "token", data: { text: "Stored value: 55." } },
        { type: "done", data: {} },
      ]),
    );
    setAccessToken("memory-access");
    vi.stubGlobal("fetch", fetchMock);
    const events: AgentSseEvent[] = [];

    for await (const event of sendMessage(
      "11000000-0000-4000-8000-000000000001",
      "Summarize the public BTC data.",
    )) {
      events.push(event);
    }

    expect(events.map(({ type }) => type)).toEqual(["meta", "token", "done"]);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/agent/conversations/11000000-0000-4000-8000-000000000001/messages",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({ content: "Summarize the public BTC data." }),
      }),
    );
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(request.headers).get("Accept")).toBe("text/event-stream");
    expect(new Headers(request.headers).get("Authorization")).toBe(
      "Bearer memory-access",
    );
  });

  it.each([
    [503, "llm_not_configured", undefined],
    [429, "rate_limited", "17"],
    [404, "conversation_not_found", undefined],
  ] as const)(
    "maps HTTP %s errors and preserves Retry-After",
    async (status, code, retryAfter) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          jsonResponse(
            { error: { code, message: "private backend detail" } },
            status,
            retryAfter ? { "Retry-After": retryAfter } : undefined,
          ),
        ),
      );

      await expect(
        sendMessage("11000000-0000-4000-8000-000000000001", "Question").next(),
      ).rejects.toMatchObject({
        name: "ApiError",
        code,
        status,
        retryAfterSeconds: retryAfter ? 17 : undefined,
      });
    },
  );

  it("uses the existing refresh flow for an unauthorized streaming request", async () => {
    document.cookie = "chaincompass_csrf=csrf-test; path=/";
    setAccessToken("old-access");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          { error: { code: "invalid_access_token", message: "hidden" } },
          401,
        ),
      )
      .mockResolvedValueOnce(jsonResponse(authResponse))
      .mockResolvedValueOnce(eventStream([{ type: "done", data: {} }]));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      sendMessage("11000000-0000-4000-8000-000000000001", "Question").next(),
    ).resolves.toEqual({ done: false, value: { type: "done", data: {} } });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/auth/refresh",
      expect.objectContaining({
        method: "POST",
        headers: { "X-CSRF-Token": "csrf-test" },
      }),
    );
  });

  it("clears the access session when a 401 cannot be refreshed", async () => {
    setAccessToken("old-access");
    const invalidated = vi.fn();
    const unsubscribe = subscribeToSessionInvalidation(invalidated);
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        { error: { code: "invalid_access_token", message: "hidden" } },
        401,
      ),
    );
    vi.stubGlobal(
      "fetch",
      fetchMock,
    );

    await expect(
      sendMessage("11000000-0000-4000-8000-000000000001", "Question").next(),
    ).rejects.toMatchObject({
      name: "ApiError",
      code: "invalid_access_token",
      status: 401,
    });
    expect(invalidated).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    unsubscribe();
  });

  it("propagates aborts instead of converting them to network errors", async () => {
    const controller = new AbortController();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_input: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_, reject) => {
            init?.signal?.addEventListener(
              "abort",
              () => reject(new DOMException("Aborted", "AbortError")),
              { once: true },
            );
          }),
      ),
    );

    const pending = sendMessage(
      "11000000-0000-4000-8000-000000000001",
      "Question",
      controller.signal,
    ).next();
    controller.abort();

    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });
});
