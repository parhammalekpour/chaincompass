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

## Allow-listed tools

The model can call only the following read-only functions. Every tool result
includes freshness metadata and `analysis_only: true`.

| Tool | Arguments |
|---|---|
| `list_chains` | None |
| `get_chain_snapshot` | `slug`: `btc`, `eth`, `sol`, or `bnb` |
| `get_score_history_summary` | `slug`: supported chain; `days`: integer from 1 to 3650 |
| `get_regime_history` | `slug`: supported chain; `limit`: integer from 1 to 20 |
| `get_scenarios` | `slug`: supported chain |
| `get_methodology_summary` | None |

Unknown names, malformed arguments, extra fields, and out-of-range values
produce safe tool errors. Tool results are delimited and treated as untrusted
data; neither tool output nor user text can extend the function allowlist.

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
orchestrator returns a structured projection of retrieved tool data and marks
the result `failed`. This check reduces unsupported output; it is not a promise
that every generated statement is correct.

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

Provider drafts are not streamed. The server checks the completed response,
performs its single revision when needed, persists the verified result, and
then sends text chunks over server-sent events. This avoids displaying a
partial response before its numeric and wording checks have completed.

Small local models may not reliably choose function calls, follow argument
schemas, or produce concise bilingual output. The provider interface keeps
model choice replaceable; quality still requires evaluation with the selected
model and deployment configuration.

## API and server-sent events

The authenticated routes are documented in [API.md](API.md). Message requests
stream `text/event-stream` events in this order: `meta`, zero or more
`tool_call` and `tool_result` pairs, verified `token` chunks, `final`, then
`done`. Provider or storage failures emit `error` and `done`. Tool-result
events contain a short status summary, not the complete result payload.

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
Live evaluation was not run as part of this implementation.
