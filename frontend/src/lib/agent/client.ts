import { z } from "zod";
import {
  apiRequest,
  apiStreamRequest,
} from "@/lib/api/client";
import {
  conversationDetailSchema,
  conversationListSchema,
  conversationSummarySchema,
  type AgentSseEvent,
  type ConversationDetail,
  type ConversationList,
  type ConversationSummary,
} from "./contracts";
import { parseSseStream } from "./sse";

function parseResponse<T>(schema: z.ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value);
  if (!result.success) {
    throw new Error("agent_contract_mismatch");
  }
  return result.data;
}

const conversationsPath = "/api/v1/agent/conversations";

export async function listConversations(): Promise<ConversationList> {
  return parseResponse(
    conversationListSchema,
    await apiRequest<unknown>(conversationsPath),
  );
}

export async function createConversation(
  title?: string,
  signal?: AbortSignal,
): Promise<ConversationSummary> {
  return parseResponse(
    conversationSummarySchema,
    await apiRequest<unknown>(conversationsPath, {
      method: "POST",
      body: title === undefined ? {} : { title },
      signal,
    }),
  );
}

export async function getConversation(
  id: string,
): Promise<ConversationDetail> {
  return parseResponse(
    conversationDetailSchema,
    await apiRequest<unknown>(
      `${conversationsPath}/${encodeURIComponent(id)}`,
    ),
  );
}

export async function deleteConversation(id: string): Promise<void> {
  await apiRequest<void>(
    `${conversationsPath}/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
}

export async function* sendMessage(
  id: string,
  content: string,
  signal?: AbortSignal,
): AsyncGenerator<AgentSseEvent> {
  const response = await apiStreamRequest(
    `${conversationsPath}/${encodeURIComponent(id)}/messages`,
    {
      method: "POST",
      body: { content },
      signal,
    },
  );
  if (!response.body) {
    throw new Error("agent_stream_unavailable");
  }
  yield* parseSseStream(response.body, signal);
}
