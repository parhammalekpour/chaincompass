import { z } from "zod";

const uuidSchema = z.string().uuid();
const dateTimeSchema = z.string().datetime({ offset: true });

export const conversationSummarySchema = z
  .object({
    id: uuidSchema,
    title: z.string().nullable(),
    created_at: dateTimeSchema,
    updated_at: dateTimeSchema,
  })
  .strict();

export const conversationListSchema = z
  .object({
    conversations: z.array(conversationSummarySchema),
  })
  .strict();

export const messageSchema = z
  .object({
    id: uuidSchema,
    role: z.enum(["user", "assistant", "tool"]),
    content: z.string(),
    tool_calls: z.array(z.record(z.string(), z.unknown())).nullable(),
    grounding_status: z.enum(["ok", "retried", "failed", "refused"]).nullable(),
    refusal: z.boolean(),
    created_at: dateTimeSchema,
  })
  .strict();

export const conversationDetailSchema = conversationSummarySchema.extend({
  messages: z.array(messageSchema),
});

export const agentMetaEventSchema = z
  .object({
    user_message_id: uuidSchema,
    assistant_message_id: uuidSchema,
    language: z.enum(["en", "fa"]),
  })
  .strict();

export const agentToolCallEventSchema = z
  .object({
    name: z.string(),
    args: z.record(z.string(), z.unknown()),
  })
  .strict();

export const agentToolResultEventSchema = z
  .object({
    name: z.string(),
    ok: z.boolean(),
    summary: z.string(),
  })
  .strict();

export const agentTokenEventSchema = z
  .object({
    text: z.string(),
  })
  .strict();

export const agentFinalEventSchema = z
  .object({
    grounding_status: z.enum(["ok", "retried", "failed", "refused"]),
    refusal: z.boolean(),
    tool_names: z.array(z.string()),
  })
  .strict();

export const agentErrorEventSchema = z
  .object({
    code: z.string(),
  })
  .strict();

export const agentDoneEventSchema = z.object({}).strict();

export type ConversationSummary = z.infer<typeof conversationSummarySchema>;
export type ConversationList = z.infer<typeof conversationListSchema>;
export type AgentMessage = z.infer<typeof messageSchema>;
export type ConversationDetail = z.infer<typeof conversationDetailSchema>;
export type GroundingStatus = NonNullable<AgentMessage["grounding_status"]>;

export type AgentSseEvent =
  | { type: "meta"; data: z.infer<typeof agentMetaEventSchema> }
  | { type: "tool_call"; data: z.infer<typeof agentToolCallEventSchema> }
  | { type: "tool_result"; data: z.infer<typeof agentToolResultEventSchema> }
  | { type: "token"; data: z.infer<typeof agentTokenEventSchema> }
  | { type: "final"; data: z.infer<typeof agentFinalEventSchema> }
  | { type: "error"; data: z.infer<typeof agentErrorEventSchema> }
  | { type: "done"; data: z.infer<typeof agentDoneEventSchema> };
