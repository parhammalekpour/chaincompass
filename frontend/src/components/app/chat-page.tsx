"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import {
  Bot,
  Check,
  CircleX,
  LoaderCircle,
  MessageSquarePlus,
  Send,
  Square,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import {
  ApiError,
  getErrorMessageKey,
  NetworkError,
} from "@/lib/api/client";
import {
  createConversation,
  deleteConversation as removeConversation,
  getConversation,
  listConversations,
  sendMessage,
} from "@/lib/agent/client";
import type {
  AgentMessage,
  AgentSseEvent,
  ConversationSummary,
  GroundingStatus,
} from "@/lib/agent/contracts";
import { formatNumber } from "@/lib/format";
import { getPublicApiErrorMessage } from "@/lib/public-api/error-codes";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isConversationId(value: string | null): value is string {
  return value !== null && UUID_PATTERN.test(value);
}

type ToolActivity = {
  id: string;
  name: string;
  status: "pending" | "complete" | "failed";
  summary: string | null;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  activities: ToolActivity[];
  groundingStatus: GroundingStatus | null;
  refusal: boolean;
};

type StreamState = {
  conversationId: string;
  controller: AbortController;
};

type RequestError =
  | { kind: "notConfigured" }
  | { kind: "rateLimited"; retryAfter: string | null }
  | { kind: "conversationNotFound" }
  | { kind: "mapped"; key: string; canRetry: boolean };

function messageFromApi(message: AgentMessage): ChatMessage | null {
  if (message.role === "tool") return null;
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    activities: [],
    groundingStatus: message.grounding_status,
    refusal: message.refusal,
  };
}

function isAbort(error: unknown, signal: AbortSignal): boolean {
  return (
    signal.aborted ||
    (error instanceof DOMException && error.name === "AbortError")
  );
}

export function ChatPage() {
  const locale = useLocale() === "fa" ? "fa" : "en";
  const t = useTranslations();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const rawConversationId = searchParams.get("c");
  const activeId = isConversationId(rawConversationId)
    ? rawConversationId
    : null;

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listFailed, setListFailed] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadedConversationId, setLoadedConversationId] = useState<
    string | null
  >(null);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [retryText, setRetryText] = useState<string | null>(null);
  const [requestError, setRequestError] = useState<RequestError | null>(null);
  const [actionError, setActionError] = useState<"delete" | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [mobileListOpen, setMobileListOpen] = useState(false);

  const streamRef = useRef<StreamState | null>(null);
  const sendLockRef = useRef(false);
  const invalidParamHandledRef = useRef(false);
  const retryIdsRef = useRef<{ userId: string; assistantId: string } | null>(
    null,
  );

  const updateConversationParam = useCallback(
    (id: string | null) => {
      const params = new URLSearchParams(searchParams.toString());
      if (id) params.set("c", id);
      else params.delete("c");
      const query = params.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, {
        scroll: false,
      });
    },
    [pathname, router, searchParams],
  );

  const loadConversations = useCallback(async () => listConversations(), []);

  const refreshConversations = useCallback(async () => {
    try {
      const result = await loadConversations();
      setConversations(result.conversations);
      setListFailed(false);
    } catch {
      setListFailed(true);
    } finally {
      setListLoading(false);
    }
  }, [loadConversations]);

  useEffect(() => {
    let current = true;
    loadConversations()
      .then((result) => {
        if (!current) return;
        setConversations(result.conversations);
        setListFailed(false);
      })
      .catch(() => {
        if (current) setListFailed(true);
      })
      .finally(() => {
        if (current) setListLoading(false);
      });
    return () => {
      current = false;
    };
  }, [loadConversations]);

  useEffect(() => {
    if (!rawConversationId || isConversationId(rawConversationId)) {
      invalidParamHandledRef.current = false;
      return;
    }
    if (invalidParamHandledRef.current) return;
    invalidParamHandledRef.current = true;
    updateConversationParam(null);
  }, [rawConversationId, updateConversationParam]);

  useEffect(() => {
    const activeStream = streamRef.current;
    if (
      activeStream &&
      activeStream.conversationId &&
      activeStream.conversationId !== activeId
    ) {
      activeStream.controller.abort();
      streamRef.current = null;
      sendLockRef.current = false;
      setStreaming(false);
    }
  }, [activeId]);

  useEffect(() => {
    if (!activeId) {
      return;
    }
    if (streamRef.current?.conversationId === activeId) return;

    let current = true;
    setDetailLoading(true);
    setRequestError(null);
    getConversation(activeId)
      .then((detail) => {
        if (!current) return;
        setLoadedConversationId(activeId);
        setMessages(
          detail.messages
            .map(messageFromApi)
            .filter((message): message is ChatMessage => message !== null),
        );
      })
      .catch((error: unknown) => {
        if (!current) return;
        if (error instanceof ApiError && error.code === "conversation_not_found") {
          setRequestError({ kind: "conversationNotFound" });
          updateConversationParam(null);
          return;
        }
        setRequestError({
          kind: "mapped",
          key: getErrorMessageKey(error),
          canRetry: error instanceof NetworkError,
        });
      })
      .finally(() => {
        if (current) setDetailLoading(false);
      });

    return () => {
      current = false;
    };
  }, [activeId, updateConversationParam]);

  useEffect(
    () => () => {
      streamRef.current?.controller.abort();
      streamRef.current = null;
    },
    [],
  );

  const stopStreaming = useCallback(
    (announceStop: boolean) => {
      const activeStream = streamRef.current;
      if (!activeStream) return;
      activeStream.controller.abort();
      streamRef.current = null;
      sendLockRef.current = false;
      setStreaming(false);
      if (announceStop) setAnnouncement(t("chatPage.stopped"));
    },
    [t],
  );

  const handleStreamEvent = useCallback(
    (
      event: AgentSseEvent,
      assistantId: string,
      controller: AbortController,
    ): boolean => {
      if (controller.signal.aborted) return false;
      if (event.type === "meta") {
        return true;
      } else if (event.type === "tool_call") {
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantId
              ? {
                  ...message,
                  activities: [
                    ...message.activities,
                    {
                      id: crypto.randomUUID(),
                      name: event.data.name,
                      status: "pending",
                      summary: null,
                    },
                  ],
                }
              : message,
          ),
        );
      } else if (event.type === "tool_result") {
        setMessages((current) =>
          current.map((message) => {
            if (message.id !== assistantId) return message;
            let updated = false;
            return {
              ...message,
              activities: message.activities.map((activity) => {
                if (
                  updated ||
                  activity.name !== event.data.name ||
                  activity.status !== "pending"
                ) {
                  return activity;
                }
                updated = true;
                return {
                  ...activity,
                  status: event.data.ok ? "complete" : "failed",
                  summary: event.data.summary,
                };
              }),
            };
          }),
        );
      } else if (event.type === "token") {
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantId
              ? { ...message, content: message.content + event.data.text }
              : message,
          ),
        );
      } else if (event.type === "final") {
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantId
              ? {
                  ...message,
                  groundingStatus: event.data.grounding_status,
                  refusal: event.data.refusal,
                }
              : message,
          ),
        );
      } else if (event.type === "error") {
        throw new Error(event.data.code);
      } else if (event.type === "done") {
        return false;
      }
      return true;
    },
    [],
  );

  const sendDraft = useCallback(
    async (rawText: string, retry = false) => {
      if (sendLockRef.current) return;
      if (!rawText.trim()) return;
      const content = rawText;
      if (Array.from(content).length > 2000) return;

      sendLockRef.current = true;
      const ids =
        retry && retryIdsRef.current
          ? retryIdsRef.current
          : {
              userId: crypto.randomUUID(),
              assistantId: crypto.randomUUID(),
            };
      retryIdsRef.current = ids;
      if (!retry) {
        setLoadedConversationId(activeId);
        setMessages((current) => [
          ...current,
          {
            id: ids.userId,
            role: "user",
            content,
            activities: [],
            groundingStatus: null,
            refusal: false,
          },
          {
            id: ids.assistantId,
            role: "assistant",
            content: "",
            activities: [],
            groundingStatus: null,
            refusal: false,
          },
        ]);
      } else {
        setMessages((current) =>
          current.map((message) =>
            message.id === ids.assistantId
              ? {
                  ...message,
                  content: "",
                  activities: [],
                  groundingStatus: null,
                  refusal: false,
                }
              : message,
          ),
        );
      }

      setDraft("");
      setRequestError(null);
      setAnnouncement("");
      setStreaming(true);
      setRetryText(null);

      const controller = new AbortController();
      let conversationId = activeId ?? "";
      streamRef.current = { conversationId, controller };
      try {
        if (!conversationId) {
          const created = await createConversation(undefined, controller.signal);
          if (controller.signal.aborted) return;
          conversationId = created.id;
          setLoadedConversationId(created.id);
          if (streamRef.current?.controller === controller) {
            streamRef.current.conversationId = conversationId;
          }
          setConversations((current) => [
            created,
            ...current.filter((item) => item.id !== created.id),
          ]);
          updateConversationParam(created.id);
        }

        let receivedDone = false;
        for await (const event of sendMessage(
          conversationId,
          content,
          controller.signal,
        )) {
          const shouldContinue = handleStreamEvent(
            event,
            ids.assistantId,
            controller,
          );
          if (!shouldContinue) {
            receivedDone = event.type === "done";
            break;
          }
        }
        if (controller.signal.aborted) return;
        if (!receivedDone) throw new Error("agent_stream_incomplete");
        setAnnouncement(t("chatPage.completed"));
        setRetryText(null);
        setListLoading(true);
        await refreshConversations();
      } catch (error) {
        if (isAbort(error, controller.signal)) return;
        const apiError = error instanceof ApiError ? error : null;
        if (apiError?.code === "llm_not_configured") {
          setRequestError({ kind: "notConfigured" });
        } else if (apiError?.code === "rate_limited") {
          const formatted = getPublicApiErrorMessage(
            "rate_limited",
            String(apiError.retryAfterSeconds ?? ""),
            locale,
          ).values?.retryAfter;
          setRequestError({
            kind: "rateLimited",
            retryAfter: formatted ?? null,
          });
        } else if (apiError?.code === "conversation_not_found") {
          setRequestError({ kind: "conversationNotFound" });
          updateConversationParam(null);
        } else {
          const key =
            error instanceof Error && error.message.startsWith("provider_")
              ? "chatPage.genericError"
              : error instanceof Error &&
                  error.message === "agent_stream_incomplete"
                ? "chatPage.genericError"
                : getErrorMessageKey(error);
          const canRetry =
            error instanceof NetworkError ||
            (apiError !== null && apiError.status >= 500) ||
            (error instanceof Error &&
              (error.message.startsWith("provider_") ||
                error.message === "agent_stream_incomplete"));
          setRequestError({ kind: "mapped", key, canRetry });
          setRetryText(canRetry ? content : null);
        }
      } finally {
        if (streamRef.current?.controller === controller) {
          streamRef.current = null;
        }
        sendLockRef.current = false;
        if (!controller.signal.aborted) setStreaming(false);
      }
    },
    [
      activeId,
      handleStreamEvent,
      locale,
      refreshConversations,
      t,
      updateConversationParam,
    ],
  );

  const createNewConversation = useCallback(async () => {
    setRequestError(null);
    setActionError(null);
    try {
      const created = await createConversation();
      setConversations((current) => [
        created,
        ...current.filter((item) => item.id !== created.id),
      ]);
      setLoadedConversationId(created.id);
      setMessages([]);
      setMobileListOpen(false);
      updateConversationParam(created.id);
    } catch (error) {
      setRequestError({
        kind: "mapped",
        key: getErrorMessageKey(error),
        canRetry: false,
      });
    }
  }, [updateConversationParam]);

  const deleteSelectedConversation = useCallback(
    async (conversation: ConversationSummary) => {
      const title =
        conversation.title || t("chatPage.untitledConversation");
      const confirmed = window.confirm(
        `${t("chatPage.confirmDeleteTitle")}\n${title}\n${t(
          "chatPage.confirmDeleteBody",
        )}`,
      );
      if (!confirmed) return;
      setActionError(null);
      if (streamRef.current?.conversationId === conversation.id) {
        stopStreaming(false);
      }
      try {
        await removeConversation(conversation.id);
        setConversations((current) =>
          current.filter((item) => item.id !== conversation.id),
        );
        if (activeId === conversation.id) {
          updateConversationParam(null);
          setMessages([]);
        }
      } catch {
        setActionError("delete");
      }
    },
    [activeId, stopStreaming, t, updateConversationParam],
  );

  const characterCount = Array.from(draft).length;
  const visibleMessages =
    (loadedConversationId ?? "") === (activeId ?? "") ? messages : [];
  const renderConversationList = (suffix: string) => (
    <section
      aria-labelledby={`chat-conversations-heading-${suffix}`}
      className="flex min-h-0 flex-col gap-3"
    >
      <div className="flex items-center justify-between gap-2">
        <h2
          id={`chat-conversations-heading-${suffix}`}
          className="font-semibold"
        >
          {t("chatPage.conversationList")}
        </h2>
        <Button
          variant="outline"
          size="icon"
          aria-label={t("chatPage.newConversation")}
          onClick={() => void createNewConversation()}
        >
          <MessageSquarePlus aria-hidden="true" />
        </Button>
      </div>
      {listLoading ? (
        <div className="space-y-2" role="status">
          <span className="sr-only">{t("chatPage.loadingConversations")}</span>
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : listFailed ? (
        <div className="space-y-2 rounded-lg border border-border bg-surface p-3">
          <p role="status" className="text-sm text-muted">
            {t("chatPage.listFailed")}
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setListLoading(true);
              void refreshConversations();
            }}
          >
            {t("states.retry")}
          </Button>
        </div>
      ) : conversations.length === 0 ? (
        <p className="rounded-lg border border-border bg-surface p-3 text-sm text-muted">
          {t("chatPage.emptyDescription")}
        </p>
      ) : (
        <ul className="max-h-[28rem] space-y-2 overflow-y-auto">
          {conversations.map((conversation) => (
            <li
              key={conversation.id}
              className="flex items-start gap-1 rounded-lg border border-border bg-surface p-2"
            >
              <button
                type="button"
                aria-current={
                  conversation.id === activeId ? "true" : undefined
                }
                className="min-w-0 flex-1 rounded-md p-2 text-start hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                onClick={() => {
                  updateConversationParam(conversation.id);
                  setMobileListOpen(false);
                }}
              >
                <span className="block truncate text-sm font-medium">
                  {conversation.title || t("chatPage.untitledConversation")}
                </span>
                <time
                  className="mt-1 block text-xs tabular-nums text-muted"
                  dateTime={conversation.updated_at}
                  dir="ltr"
                >
                  {conversation.updated_at.slice(0, 10)}
                </time>
              </button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={t("chatPage.deleteConversationLabel", {
                  title:
                    conversation.title || t("chatPage.untitledConversation"),
                })}
                onClick={() => void deleteSelectedConversation(conversation)}
              >
                <Trash2 aria-hidden="true" />
              </Button>
            </li>
          ))}
        </ul>
      )}
      {actionError === "delete" && (
        <p role="alert" className="rounded-lg border border-border p-3 text-sm">
          {t("chatPage.deleteFailed")}
        </p>
      )}
    </section>
  );

  const retryAfterError =
    requestError?.kind === "rateLimited"
      ? requestError.retryAfter
        ? t("chatPage.rateLimited", { retryAfter: requestError.retryAfter })
        : t("chatPage.rateLimitedNoRetry")
      : null;

  return (
    <main
      lang={locale}
      dir={locale === "fa" ? "rtl" : "ltr"}
      className="mx-auto max-w-7xl space-y-5"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("chatPage.title")}
          </h1>
          <p className="text-sm text-muted">{t("chatPage.description")}</p>
        </div>
        <Button
          variant="outline"
          className="hidden gap-2 md:inline-flex"
          onClick={() => void createNewConversation()}
        >
          <MessageSquarePlus aria-hidden="true" />
          {t("chatPage.newConversation")}
        </Button>
      </header>

      <div className="md:hidden">
        <Button
          variant="outline"
          aria-expanded={mobileListOpen}
          aria-controls="chat-mobile-conversation-list"
          onClick={() => setMobileListOpen((open) => !open)}
        >
          {mobileListOpen
            ? t("chatPage.hideConversations")
            : t("chatPage.showConversations")}
        </Button>
        {mobileListOpen && (
          <div
            id="chat-mobile-conversation-list"
            className="mt-3 rounded-xl border border-border bg-background p-3"
          >
            {renderConversationList("mobile")}
          </div>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-[17rem_minmax(0,1fr)]">
        <aside className="hidden rounded-xl border border-border bg-background p-3 md:block">
          {renderConversationList("desktop")}
        </aside>

        <section
          aria-label={t("chatPage.title")}
          className="flex min-h-[32rem] min-w-0 flex-col rounded-xl border border-border bg-background"
        >
          <div className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-5">
            {activeId && detailLoading ? (
              <div className="space-y-3" role="status">
                <span className="sr-only">{t("chatPage.loadingMessages")}</span>
                <Skeleton className="h-16 w-3/4" />
                <Skeleton className="ms-auto h-24 w-3/4" />
              </div>
            ) : visibleMessages.length > 0 ? (
              visibleMessages.map((message) => (
                <article
                  key={message.id}
                  className={`max-w-[95%] space-y-2 rounded-xl border border-border p-3 sm:max-w-[85%] ${
                    message.role === "user"
                      ? "ms-auto bg-surface"
                      : "me-auto bg-background"
                  }`}
                >
                  <p className="text-xs font-medium text-muted">
                    {t(
                      message.role === "user"
                        ? "chatPage.you"
                        : "chatPage.assistant",
                    )}
                  </p>
                  {message.activities.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {message.activities.map((activity) => (
                        <span
                          key={activity.id}
                          className="inline-flex max-w-full items-center gap-1 rounded-full border border-border bg-surface px-2.5 py-1 text-xs"
                        >
                          {activity.status === "pending" ? (
                            <LoaderCircle
                              aria-hidden="true"
                              className="size-3.5 animate-spin"
                            />
                          ) : activity.status === "complete" ? (
                            <Check aria-hidden="true" className="size-3.5" />
                          ) : (
                            <CircleX aria-hidden="true" className="size-3.5" />
                          )}
                          <span>
                            {t(
                              activity.status === "pending"
                                ? "chatPage.toolLookup"
                                : activity.status === "complete"
                                  ? "chatPage.toolDone"
                                  : "chatPage.toolFailed",
                              {
                              tool: isKnownTool(activity.name)
                                ? t(`chatPage.tools.${activity.name}`)
                                : t("chatPage.toolUnknown"),
                              },
                            )}
                          </span>
                          {activity.summary && (
                            <span dir="auto" className="text-muted">
                              {activity.summary}
                            </span>
                          )}
                        </span>
                      ))}
                    </div>
                  )}
                  {message.content && (
                    <p
                      dir="auto"
                      className="whitespace-pre-wrap break-words leading-6"
                    >
                      {message.content}
                    </p>
                  )}
                  {message.groundingStatus === "retried" && (
                    <p className="rounded-lg border border-border bg-surface p-2 text-sm text-muted">
                      {t("chatPage.retriedNotice")}
                    </p>
                  )}
                  {message.groundingStatus === "failed" && (
                    <p className="rounded-lg border border-border bg-surface p-2 text-sm text-muted">
                      {t("chatPage.failedNotice")}
                    </p>
                  )}
                  {message.refusal && (
                    <Card className="border border-border bg-surface">
                      <CardHeader>
                        <CardTitle>{t("chatPage.refusalTitle")}</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <p className="text-muted">
                          {t("chatPage.refusalDescription")}
                        </p>
                        <div className="flex flex-wrap gap-3">
                          <Link
                            href="/app/chains"
                            className="underline underline-offset-4"
                          >
                            {t("chatPage.chainsLink")}
                          </Link>
                          <Link
                            href="/methodology"
                            className="underline underline-offset-4"
                          >
                            {t("chatPage.methodologyLink")}
                          </Link>
                        </div>
                      </CardContent>
                    </Card>
                  )}
                  {streaming &&
                    message.role === "assistant" &&
                    !message.content &&
                    message.activities.length === 0 && (
                      <p role="status" className="text-sm text-muted">
                        <Bot
                          aria-hidden="true"
                          className="me-1 inline size-4"
                        />
                        {t("chatPage.checkingData")}
                      </p>
                    )}
                </article>
              ))
            ) : !activeId ? (
              <div className="mx-auto max-w-2xl space-y-4 py-8">
                <div className="space-y-2 text-center">
                  <h2 className="text-xl font-semibold">
                    {t("chatPage.emptyTitle")}
                  </h2>
                  <p className="text-sm text-muted">
                    {t("chatPage.emptyDescription")}
                  </p>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {starterQuestions(t).map(
                    (question) => (
                      <Button
                        key={question}
                        type="button"
                        variant="outline"
                        className="h-auto min-h-12 justify-start whitespace-normal p-3 text-start"
                        onClick={() => setDraft(question)}
                      >
                        {question}
                      </Button>
                    ),
                  )}
                </div>
              </div>
            ) : (
              <div className="mx-auto max-w-md space-y-2 py-12 text-center">
                <h2 className="text-lg font-semibold">
                  {requestError?.kind === "conversationNotFound"
                    ? t("authErrors.conversationNotFound")
                    : t("chatPage.noConversationTitle")}
                </h2>
                <p className="text-sm text-muted">
                  {requestError?.kind === "conversationNotFound"
                    ? t("chatPage.conversationNotFound")
                    : t("chatPage.noConversationDescription")}
                </p>
              </div>
            )}

            {requestError?.kind === "notConfigured" && (
              <Card className="border border-border bg-surface">
                <CardHeader>
                  <CardTitle>{t("chatPage.notConfiguredTitle")}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted">
                    {t("chatPage.notConfiguredDescription")}
                  </p>
                </CardContent>
              </Card>
            )}
            {retryAfterError && (
              <p role="alert" className="rounded-lg border border-border bg-surface p-3 text-sm">
                {retryAfterError}
              </p>
            )}
            {requestError?.kind === "conversationNotFound" && (
              <p role="alert" className="rounded-lg border border-border bg-surface p-3 text-sm">
                {t("chatPage.conversationNotFound")}
              </p>
            )}
            {requestError?.kind === "mapped" && (
              <div
                role="alert"
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-3 text-sm"
              >
                <span>{t(requestError.key)}</span>
                {requestError.canRetry && retryText && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void sendDraft(retryText, true)}
                  >
                    {t("chatPage.retry")}
                  </Button>
                )}
              </div>
            )}
          </div>

          <div className="space-y-3 border-t border-border p-3 sm:p-4">
            <p className="text-xs leading-5 text-muted">
              {t("chatPage.privacyNotice")}{" "}
              <Link
                href="/legal#privacy"
                className="underline underline-offset-4"
              >
                {t("chatPage.legalPrivacyLink")}
              </Link>
            </p>
            <form
              className="space-y-2"
              onSubmit={(event) => {
                event.preventDefault();
                void sendDraft(draft);
              }}
            >
              <label
                htmlFor="chat-composer"
                className="text-sm font-medium"
              >
                {t("chatPage.composerLabel")}
              </label>
              <textarea
                id="chat-composer"
                dir="auto"
                value={draft}
                disabled={streaming}
                rows={3}
                placeholder={t("chatPage.composerPlaceholder")}
                onChange={(event) => {
                  const value = event.target.value;
                  setDraft(Array.from(value).slice(0, 2000).join(""));
                }}
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter" &&
                    !event.shiftKey &&
                    !event.nativeEvent.isComposing
                  ) {
                    event.preventDefault();
                    void sendDraft(draft);
                  }
                }}
                className="w-full resize-y rounded-lg border border-border bg-background px-3 py-2 text-sm leading-6 outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
              />
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span
                  dir="ltr"
                  className="text-xs tabular-nums text-muted"
                  aria-live="off"
                >
                  {t("chatPage.characterCount", {
                    count: formatNumber(characterCount, locale),
                  })}
                </span>
                {streaming ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => stopStreaming(true)}
                  >
                    <Square aria-hidden="true" />
                    {t("chatPage.stop")}
                  </Button>
                ) : (
                  <Button
                    type="submit"
                    variant="outline"
                    disabled={
                      !draft.trim() || characterCount > 2000 || detailLoading
                    }
                  >
                    <Send aria-hidden="true" />
                    {t("chatPage.send")}
                  </Button>
                )}
              </div>
            </form>
          </div>
        </section>
      </div>
      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
    </main>
  );
}

function starterQuestions(t: ReturnType<typeof useTranslations>): string[] {
  const questions = t.raw("chatPage.starterQuestions");
  return Array.isArray(questions)
    ? questions.filter((question): question is string =>
        typeof question === "string",
      )
    : [];
}

function isKnownTool(
  name: string,
): name is
  | "list_chains"
  | "get_chain_snapshot"
  | "get_score_history_summary"
  | "get_regime_history"
  | "get_scenarios"
  | "get_methodology_summary" {
  return [
    "list_chains",
    "get_chain_snapshot",
    "get_score_history_summary",
    "get_regime_history",
    "get_scenarios",
    "get_methodology_summary",
  ].includes(name);
}
