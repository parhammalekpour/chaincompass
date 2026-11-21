import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { parseSseChunks, parseSseStream } from "./sse";
import type { AgentSseEvent } from "./contracts";

async function* fromStrings(chunks: string[]) {
  yield* chunks;
}

async function collect(
  chunks: AsyncIterable<string>,
): Promise<AgentSseEvent[]> {
  const events: AgentSseEvent[] = [];
  for await (const event of parseSseChunks(chunks)) events.push(event);
  return events;
}

describe("agent SSE parser", () => {
  it("parses each backend event payload from the synthetic fixture", async () => {
    const fixture = readFileSync(
      resolve(process.cwd(), "src/test/fixtures/agent-events.sse"),
      "utf8",
    );
    const events = await collect(fromStrings([fixture]));

    expect(events.map(({ type }) => type)).toEqual([
      "meta",
      "tool_call",
      "tool_result",
      "token",
      "final",
      "done",
    ]);
    expect(events[1]).toEqual({
      type: "tool_call",
      data: { name: "get_chain_snapshot", args: { slug: "btc" } },
    });
  });

  it("handles CRLF split across chunks, comments, multiple data lines and events", async () => {
    const events = await collect(
      fromStrings([
        "event: token\r",
        '\n: keepalive\r\ndata: {\r\ndata: "text": "one"\r\n',
        'data: }\r\n\r\nevent: done\ndata: {}\n\n',
      ]),
    );

    expect(events).toEqual([
      { type: "token", data: { text: "one" } },
      { type: "done", data: {} },
    ]);
  });

  it("dispatches a trailing partial event at end of stream", async () => {
    await expect(
      collect(fromStrings(['event: token\ndata: {"text":"tail"}'])),
    ).resolves.toEqual([{ type: "token", data: { text: "tail" } }]);
  });

  it("emits an error event for invalid JSON and ignores unknown event names", async () => {
    const events = await collect(
      fromStrings([
        "event: token\ndata: {bad json}\n\n",
        "event: future_type\ndata: {}\n\n",
      ]),
    );

    expect(events).toEqual([
      { type: "error", data: { code: "invalid_sse_json" } },
    ]);
  });

  it("decodes UTF-8 characters split across byte chunks in streaming mode", async () => {
    const encoded = new TextEncoder().encode(
      'event: token\ndata: {"text":"داده"}\n\n',
    );
    const splitAt = encoded.findIndex((byte) => byte > 0x7f) + 1;
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoded.slice(0, splitAt));
        controller.enqueue(encoded.slice(splitAt));
        controller.close();
      },
    });
    const events: AgentSseEvent[] = [];
    for await (const event of parseSseStream(stream)) events.push(event);

    expect(events).toEqual([{ type: "token", data: { text: "داده" } }]);
  });
});
