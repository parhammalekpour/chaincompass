import {
  agentDoneEventSchema,
  agentErrorEventSchema,
  agentFinalEventSchema,
  agentMetaEventSchema,
  agentTokenEventSchema,
  agentToolCallEventSchema,
  agentToolResultEventSchema,
  type AgentSseEvent,
} from "./contracts";

const invalidJsonEvent: AgentSseEvent = {
  type: "error",
  data: { code: "invalid_sse_json" },
};
const invalidPayloadEvent: AgentSseEvent = {
  type: "error",
  data: { code: "invalid_sse_payload" },
};

function decodeEvent(name: string, lines: string[]): AgentSseEvent | null {
  const schema = {
    meta: agentMetaEventSchema,
    tool_call: agentToolCallEventSchema,
    tool_result: agentToolResultEventSchema,
    token: agentTokenEventSchema,
    final: agentFinalEventSchema,
    error: agentErrorEventSchema,
    done: agentDoneEventSchema,
  }[name];
  if (!schema) return null;

  let payload: unknown;
  try {
    payload = JSON.parse(lines.join("\n"));
  } catch {
    return invalidJsonEvent;
  }
  const parsed = schema.safeParse(payload);
  if (!parsed.success) return invalidPayloadEvent;
  return { type: name, data: parsed.data } as AgentSseEvent;
}

export async function* parseSseChunks(
  chunks: AsyncIterable<string>,
): AsyncGenerator<AgentSseEvent> {
  let buffer = "";
  let eventName = "";
  let dataLines: string[] = [];

  const dispatch = (): AgentSseEvent | null => {
    if (dataLines.length === 0) {
      eventName = "";
      return null;
    }
    const event = decodeEvent(eventName || "message", dataLines);
    eventName = "";
    dataLines = [];
    return event;
  };

  const processLine = (line: string): AgentSseEvent | null => {
    if (line === "") return dispatch();
    if (line.startsWith(":")) return null;

    const separator = line.indexOf(":");
    const field = separator < 0 ? line : line.slice(0, separator);
    let value = separator < 0 ? "" : line.slice(separator + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") eventName = value;
    if (field === "data") dataLines.push(value);
    return null;
  };

  for await (const chunk of chunks) {
    buffer += chunk;
    while (buffer.length > 0) {
      const lineEnd = buffer.search(/[\r\n]/);
      if (lineEnd < 0) break;
      if (
        buffer[lineEnd] === "\r" &&
        lineEnd === buffer.length - 1
      ) {
        break;
      }
      const line = buffer.slice(0, lineEnd);
      const terminatorLength =
        buffer[lineEnd] === "\r" && buffer[lineEnd + 1] === "\n" ? 2 : 1;
      buffer = buffer.slice(lineEnd + terminatorLength);
      const event = processLine(line);
      if (event) yield event;
    }
  }

  if (buffer.endsWith("\r")) {
    const event = processLine(buffer.slice(0, -1));
    if (event) yield event;
    buffer = "";
  }
  if (buffer.length > 0) {
    const event = processLine(buffer);
    if (event) yield event;
  }
  const trailingEvent = dispatch();
  if (trailingEvent) yield trailingEvent;
}

function abortError(signal: AbortSignal): Error {
  return signal.reason instanceof Error
    ? signal.reason
    : new DOMException("The operation was aborted", "AbortError");
}

export async function* parseSseStream(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<AgentSseEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let finished = false;

  async function* decodedChunks(): AsyncGenerator<string> {
    try {
      while (true) {
        if (signal?.aborted) throw abortError(signal);
        const { done, value } = await reader.read();
        if (done) {
          finished = true;
          const tail = decoder.decode();
          if (tail) yield tail;
          return;
        }
        yield decoder.decode(value, { stream: true });
      }
    } finally {
      if (!finished) await reader.cancel().catch(() => undefined);
      reader.releaseLock();
    }
  }

  yield* parseSseChunks(decodedChunks());
}
