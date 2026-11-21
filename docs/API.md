# Public Data API

The public API is read-only and requires no login. All routes are `GET` under
`/api/v1`; they expose chain analytics, not advice or predictions. The API does
not expose authentication, admin, ingestion-run, RPC-probe, or provider-error
details.

## Endpoints

| Method | Path | Parameters | Response model |
|---|---|---|---|
| GET | `/api/v1/chains` | — | `ChainsResponse` |
| GET | `/api/v1/chains/{slug}` | `as_of` (optional ISO date) | `ChainDetailResponse` |
| GET | `/api/v1/chains/{slug}/score-history` | `from`, `to` (optional ISO dates) | `ScoreHistoryResponse` |
| GET | `/api/v1/chains/{slug}/regimes` | `from`, `to` (optional ISO dates) | `RegimesResponse` |
| GET | `/api/v1/chains/{slug}/series` | `metric` (required), `source` (conditional), `from`, `to` | `SeriesResponse` |
| GET | `/api/v1/chains/{slug}/scenarios` | `as_of` (optional ISO date) | `ScenariosResponse` |
| GET | `/api/v1/methodology` | — | `MethodologyResponse` |

`slug` is one of `btc`, `eth`, `sol`, or `bnb`. Every response includes a UTC
`generated_at` and `analysis_only: true`. Decimal values are JSON strings;
dates use ISO `YYYY-MM-DD`. Missing observations remain missing.

## Current score date and snapshots

Each chain's current score is its latest computed score row. A partial latest
score is **not** backdated: it includes `coverage`, registry-derived
`coverage_max`, `is_partial`, and `confidence_label`. Chain detail includes
`last_full_coverage` only when the selected score is partial; it identifies the
most recent earlier score at maximum registry coverage, or is `null` if none
exists. Maximum coverage is BTC `0.7000`, ETH `0.9000`, SOL `0.6000`, and BNB
`0.6000`.

`GET /chains/{slug}?as_of=YYYY-MM-DD` selects a score row for exactly that
date. A date without a score row returns `404 no_snapshot_for_date`; a future
date returns `422`. Price observations in a snapshot are constrained to that
date or earlier. When `as_of` is supplied, `data_coverage` reports observations
available through that date; without it, coverage metadata is current.

Example, shortened:

```json
{
  "generated_at": "2026-11-20T16:30:00Z",
  "analysis_only": true,
  "slug": "btc",
  "price": {"close_usd": "81000.000000000000", "as_of_date": "2026-11-19", "ret_30d": "0.025000000000"},
  "score": {
    "value": "53.75",
    "as_of_date": "2026-11-19",
    "coverage": "0.6000",
    "coverage_max": "0.7000",
    "is_partial": true,
    "confidence_label": "Medium",
    "version": "v1",
    "pillars": {"market_condition": {"score": "55.000000000000", "weight_used": 30, "available": true}},
    "components": [{"feature": "drawdown_365d", "value": "-0.20", "percentile": "55.0", "weight": 10, "direction": "higher_is_better"}]
  },
  "last_full_coverage": {
    "value": "55.50",
    "as_of_date": "2026-11-18",
    "coverage": "0.7000",
    "confidence_label": "Medium"
  }
}
```

Scores are relative to each chain's own history, and component sets differ by
chain. Show confidence with every score; cross-chain comparisons are
indicative only.

## History, regimes, and raw series

- Score history defaults to the 365 days ending on that chain's latest score
  date. Explicit ranges are ascending and limited to 3,650 days.
- Regimes are run-length segments of stored reported labels. Any missing day
  splits a segment; `days` is the number of consecutive daily rows. The response
  also includes the latest stored volatility state.
- Raw series defaults to the latest 365 days ending on that series' last
  observation date and returns at most 5,000 points. It does not fill gaps.
  `meta.first_date`, `meta.last_date`, `meta.points`, and `meta.missing` describe
  the stored series coverage; `points` is the requested date-range result.
- `metric` and `source` must match the public series registry. If a metric has
  multiple sources, `source` is required and a 422 lists valid choices.
  `role` distinguishes score inputs from context-only data; `derived` marks
  derived series such as BTC `fees_usd`. Each series includes a unit note and
  coverage status. Chain detail's `data_coverage` includes registered
  unavailable/discontinued entries as non-score context; it contains no
  provider error text. DefiLlama unit semantics remain UNVERIFIED.
- Unavailable and discontinued series return `404 series_not_available` with a
  safe reason. For example, legacy BNB Coin Metrics data is not BNB Chain.

Example series response, shortened:

```json
{
  "generated_at": "2026-11-20T16:30:00Z",
  "analysis_only": true,
  "meta": {"chain": "btc", "metric": "fees_usd", "source": "blockchain_info", "role": "score", "derived": true, "status": "ok", "points": 2, "missing": 0, "unit_note": "Derived USD estimate"},
  "points": [{"date": "2026-11-17", "value": "10.000000000000"}, {"date": "2026-11-18", "value": "12.000000000000"}]
}
```

## Historical-return scenarios

`GET /api/v1/chains/{slug}/scenarios` reports descriptive historical return
quantiles for 30-, 90-, and 365-calendar-day horizons. By default, `as_of_date`
is the latest Binance close date for the chain. An explicit `as_of` must have
an exact Binance close row; a missing row returns `404 no_snapshot_for_date`,
and a future date returns `422`.

For horizon `H`, each realised return uses exact closes at dates `d` and
`d + H`:

```text
return(d, H) = close(d + H) / close(d) - 1
```

Only windows whose end date is on or before `as_of_date` are included. Both
endpoint closes must exist; missing days are not filled. The engine uses all
eligible history from the chain's first price. Returns are rounded to six
decimal places.

Quantiles use Hyndman-Fan type 7 with Decimal arithmetic. Sort returns as
`x[0] <= ... <= x[n-1]`; for probability `p`, compute `h = (n - 1) * p`,
`j = floor(h)`, `k = min(j + 1, n - 1)`, and
`Q(p) = x[j] + (h - j) * (x[k] - x[j])`. Scenario mapping is fixed:
pessimistic = p10, base = p50, optimistic = p90.
`illustrative_price_usd` is the latest eligible close multiplied by
`1 + return`; it is a historical-return illustration, not a forecast.

`n_independent = n_windows // horizon_days` is a conservative effective-sample
count because adjacent windows overlap. Fewer than 5 independent windows makes
the horizon unavailable with `reason: "insufficient_history"`; counts and
window dates remain visible, while `share_negative` is null and `scenarios`
is empty. From 5 to 9 independent windows, results are available with
`low_sample: true`; 10 or more is the normal sample state. `share_negative`
counts strictly negative window returns and is rounded to four decimal places.
All return and price numbers are Decimal strings.

Every response carries `not_a_forecast: true`, `analysis_only: true`, a method
note, and a disclaimer. These results describe historical outcomes only; they
are not a forecast or financial advice. The `/chains/{slug}` detail response
does not embed a scenario summary; use the dedicated endpoint.

## Methodology

`GET /api/v1/methodology` is generated from the v1 score configuration and
reports percentile windows, components and weights, coverage/confidence
thresholds, registry-derived maximum coverage, regime and volatility rules,
risk-flag rules, scenario horizons/quantiles/sample gates, source homepages and
terms notes, and known limitations. Scenario parameters are generated from
the same configuration used by the pure engine.

## Errors and operational limits

Errors use the same envelope:

```json
{"error": {"code": "series_not_available", "message": "Reason"}}
```

Relevant codes include `chain_not_found`, `no_snapshot_for_date`,
`series_not_available`, `source_required`, `validation_error`,
`future_as_of_date`, `invalid_date_range`, `range_too_large`, `too_many_points`,
and `rate_limited`.
Date parsing and range validation return 422; unknown chains, missing snapshots,
and unavailable series return 404.

All successful public API responses use
`Cache-Control: public, max-age=300, stale-while-revalidate=600`. Routes share
an in-process per-IP sliding-window limit of 120 requests per minute. The
limit is per API process (not distributed across multiple workers); 429
responses include `Retry-After`.

## Authenticated agent API

Agent routes require an authenticated access token and scope every conversation
to its owner. Unknown and non-owned conversation IDs both return 404.

| Method | Path | Response |
|---|---|---|
| POST | `/api/v1/agent/conversations` | 201 and the created conversation |
| GET | `/api/v1/agent/conversations` | The current user's conversations |
| GET | `/api/v1/agent/conversations/{id}` | Conversation and messages |
| DELETE | `/api/v1/agent/conversations/{id}` | 204 |
| POST | `/api/v1/agent/conversations/{id}/messages` | `text/event-stream` |

Non-refusal message requests return `503 llm_not_configured` when no provider is
configured; restricted requests can receive a deterministic response without
a provider. In-process per-user limits are 20 messages per hour and 100 per
day; `429` responses include `Retry-After`. A user may create at most 50
conversations, each with at most 200 messages. The daily token budget defaults
to 200,000 and is checked when provider usage counts are available.

Successful message streams include a `meta` event, optional `tool_call` and
`tool_result` events, verified `token` chunks, a `final` event, and `done`.
Tool-result events contain only a short status summary. Failures send `error`
and `done`. Responses use `Cache-Control: no-cache` and
`X-Accel-Buffering: no`.

Synthetic event sequence:

```text
event: meta
data: {"user_message_id":"00000000-0000-0000-0000-000000000001","assistant_message_id":"00000000-0000-0000-0000-000000000002","language":"en"}

event: tool_call
data: {"name":"get_chain_snapshot","args":{"slug":"btc"}}

event: tool_result
data: {"name":"get_chain_snapshot","ok":true,"summary":"data_returned"}

event: token
data: {"text":"The stored score is 55."}

event: final
data: {"grounding_status":"ok","refusal":false,"tool_names":["get_chain_snapshot"]}

event: done
data: {}
```

Conversation messages are stored and sent to the configured provider for
processing. See [AGENT.md](AGENT.md) for tool schemas, verification rules,
operational limits, and evaluation instructions.
