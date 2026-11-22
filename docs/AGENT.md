# Agent backend

The agent backend is a user-scoped, read-only interface over public ChainCompass
data. It uses the same service functions as the public API rather than making
HTTP requests back into the application. The agent has no user-data tools and
cannot write application data through its tool set.

## Provider configuration

`LLM_PROVIDER` accepts `none`, `fake`, or `openai_compatible`. The default is
`none`; non-refusal message requests then return `503 llm_not_configured`.
Restricted requests can receive a deterministic response without a provider.
The compatible provider reads `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`.
Configure an OpenAI-compatible endpoint only when it is available and
appropriate for your deployment. Provider requests have a 60-second ceiling
and retry once after a timeout or server error. Credentials, request bodies,
and message content are not written to application logs.
For OpenRouter, use `https://openrouter.ai/api/v1` as the base URL and select a
model that supports tool calling; the provider appends `/chat/completions` and
sends the key as a Bearer token. Local setup steps are in [SETUP.md](SETUP.md).

## Allow-listed tools

The model can call only the following read-only functions. Every tool result
includes freshness metadata and `analysis_only: true`.

| Tool | Arguments |
|---|---|
| `list_chains` | None |
| `get_chain_snapshot` | `slug`: `btc`, `eth`, `sol`, or `bnb` |
| `get_fundamental_report` | `slug`: supported chain |
| `get_score_history_summary` | `slug`: supported chain; `days`: integer from 1 to 3650 |
| `get_regime_history` | `slug`: supported chain; `limit`: integer from 1 to 20 |
| `get_scenarios` | `slug`: supported chain |
| `get_methodology_summary` | None |

Unknown names, malformed arguments, extra fields, and out-of-range values
produce safe tool errors. Tool results are delimited and treated as untrusted
data; neither tool output nor user text can extend the function allowlist.
The report tool returns stored scores, regimes, flags, and indicator gaps. Its
compact summary is assembled by application code; the model does not create
report values.

## Grounding and response checks

The final response is checked before any text is sent to the client:

1. Persian and Arabic-Indic digits are normalized to Latin digits.
2. ISO dates, list ordinals, `/100`, day-window labels `30`, `90`, `365`, and
   `1095`, and percentile labels `p10`, `p50`, and `p90` are structural and are
   ignored.
3. Every other numeric token must match a number in this turn's tool results,
   either exactly or after half-up rounding to the number of decimal places
   shown in the answer. A percentage may also match a source value multiplied
   by 100.
4. Numeric values are compared as `Decimal`. Floats are accepted only at the
   grounding-comparison boundary and are converted through their decimal text
   representation.

The output check also rejects prohibited wording. A failed check prompts one
revision with the offending terms or numbers. If that still fails, the
orchestrator returns a short, localized plain-text summary of the verified
figures returned by this turn's tools and marks the result `failed`. The first
line explains that the assistant's wording could not be verified; known tools
have deterministic formatters, and an unknown tool is represented by a generic
retrieval line. Raw JSON is not shown. If no usable tool result exists, the
existing safe no-data message is returned.

Grounding matches a number against any value in any tool result from this turn;
it does not bind a claim to a specific chain or metric. For example, a number
returned for BTC could validate a numeric claim about ETH. This limitation is
known and has not been changed. The check reduces unsupported output; it is not
a promise that every generated statement is correct.
Any number present in this turn's tool results can validate an answer number,
including numbers from `get_fundamental_report`; values are not tied to a
specific report field or chain by the grounding check.

Input classification handles restricted financial-direction requests with a
deterministic bilingual response before provider access. The system prompt
requires analysis-only language, tool-backed numbers, uncertainty context for
scores and scenarios, Latin digits, and the user's language. Prompt-injection
content is treated as data, not instructions. The request limit is 2,000
characters; orchestration allows at most four tool iterations and four tool
calls within a 60-second total budget.

## Conversations, limits, and privacy

All conversation endpoints require an authenticated access token and enforce
ownership; an unknown or another user's conversation returns `404`. Each
account can have at most 50 conversations, with at most 200 messages per
conversation. In-process rate limits allow 20 messages per hour and 100 per
day; these limits are per API process. The default daily token budget is
200,000 tokens when the provider supplies usage counts.

Conversation messages, tool results, and verified assistant responses are
stored in PostgreSQL. `llm_usage` stores provider/model labels, token counts,
latency, status, and timestamps, but no message content. Messages are sent to
the configured language-model provider for processing. A user-facing chat
interface must explain this data flow before it is made available.

## Why verify, then stream

Provider drafts are not streamed. The server emits `meta` immediately, then
emits each `tool_call` before execution and its `tool_result` immediately after
the tool finishes. These progress events can arrive while the provider loop is
still running. Assistant `token` events are sent only after the completed
response has passed numeric and wording checks, or after the deterministic
fallback has been selected; the verified result is persisted before tokens.
This keeps unverified assistant text out of the stream while still showing
live tool activity.

Small local models may not reliably choose function calls, follow argument
schemas, or produce concise bilingual output. The provider interface keeps
model choice replaceable; quality still requires evaluation with the selected
model and deployment configuration.

## API and server-sent events

The authenticated routes are documented in [API.md](API.md). Message requests
stream `text/event-stream` events in this order: `meta`, zero or more
`tool_call` and `tool_result` pairs, verified `token` chunks, `final`, then
`done`. Each tool event is sent as the corresponding work happens, including
tool executions across provider iterations; a single execution emits one pair.
Provider or storage failures emit `error` and `done`. Tool-result events
contain a short status summary, not the complete result payload. The response
uses `Cache-Control: no-cache, no-transform` and `X-Accel-Buffering: no`.
`no-transform` prevents Next's rewrite path from compressing the event stream;
keep Next compression enabled for ordinary responses and ensure deployment
reverse proxies honor this directive. The installed Next proxy timeout is
65 seconds, above the agent's 60-second orchestration budget, so a valid stream
is not cut off early.

## Offline evaluation

Run the deterministic, network-free evaluation from `backend`:

```powershell
& .\.venv\Scripts\python.exe -m app.agent.eval
```

The committed bilingual cases cover refusal classification, allowed tool
plans, grounding and rounding, injection in user and tool data, restricted
tool names, output checks, and Persian digits. The CLI reports pass/fail counts
by category and exits nonzero if any case fails.

An opt-in `--live` mode runs only allowed analysis cases with the configured
OpenAI-compatible provider. It requires `RUN_LLM_EVAL=1`, provider
configuration, and database access, and writes case identifiers and
verification outcomes (not prompts or responses) under `docs/agent-eval/`.
The opt-in live evaluation mode was not run as part of this implementation; a
separate smoke check is documented below and is not an evaluation.

## Live check (2026-11-22)

A separate fixed 12A2 smoke check used `openai_compatible` via OpenRouter with
model `google/gemini-2.5-flash-lite`. It sent 11 messages: 10 provider-calling
messages and one deterministic refusal. This was a tiny smoke check, not a model
evaluation; results depend on the model and day.

All nine messages with an expected tool plan invoked the expected tool(s), and
the ten persisted tool invocations had schema-valid arguments. Grounding was
`ok` for 6 messages, `retried` for 1, and `failed` for 3; the deterministic
fallback was used for those 3 failed messages. The refusal produced no provider
call. The unsupported-chain request produced no tool call or numeric answer.
Four manual numeric spot checks matched same-chain public API values, with no
wrong-chain mismatch observed; the BNB answer gave the matching 90-day range
but did not state the net change. The prompt-disclosure marker check found no
disclosure, though that response was not independently reviewed.

Observed provider latency was 630–9,657 ms (median 2,179 ms); usage totalled
34,896 prompt and 3,536 completion tokens. Language-script checks matched all
11 requested languages; Persian quality was judged by a non-native reviewer
and is UNVERIFIED. Windows console encoding failed while serializing the final
report, so outcomes were recovered from persisted messages and usage; SSE
arrival timings and detailed provider error codes were not retained. No HTTP
429 or timeout was observed; other provider errors are unverified.

This tiny smoke check is not a model evaluation or a claim of predictive or
language quality. Results are model- and day-dependent.
