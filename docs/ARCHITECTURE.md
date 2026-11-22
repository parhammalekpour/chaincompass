# Architecture

```text
                         +--------------------+
                         |      Browser       |
                         +---------+----------+
                                   |
                                   v
                         +--------------------+
                         | Next.js frontend   |
                         | same-origin /api   |
                         | rewrite            |
                         +---------+----------+
                                   |
                                   v
                         +--------------------+
                         | FastAPI            |
                         +----+----------+----+
                              |          |
                   +----------v--+    +--v----------------------+
                   | PostgreSQL  |    | LLM provider + agent  |
                   +-----^------+    | API                    |
                         |           +------------------------+
                         |
              +----------+----------+
              | Worker (APScheduler)|
              +----------+----------+
                         |
                         v
              +--------------------------+
              | Data sources             |
              | DefiLlama, CoinGecko,    |
              | Coin Metrics, etc.       |
              +--------------------------+

       Planned: alert delivery (email/Telegram)
```

The browser and API share one development origin: Next.js forwards `/api` to
FastAPI. FastAPI serves validated application requests and reads/writes
PostgreSQL. A separate APScheduler worker collects and normalizes data from
swappable external providers before storing them. Account emails are handled by
the auth email sender. The backend includes a replaceable language-model
provider interface and an authenticated agent API with a bilingual chat UI.
The authenticated watchlist, alert-rule, event-storage, and daily-evaluation
backend is implemented. Its frontend and email/Telegram delivery are planned.

## Implemented vs Planned

Implemented: bilingual Next.js routes and auth UI, the dashboard, FastAPI
health/auth/admin endpoints, the public read-only data API under `/api/v1`,
ingestion providers, the separate APScheduler worker, RPC probes, and the
point-in-time feature engine with its CLI, plus a pure historical-return
scenario engine and public scenario endpoint. The app also includes a localized
chain detail page with independently loaded snapshot, history, regime, price,
and scenario sections.

The Network Health Score, regimes, and risk flags are implemented in the
backend scoring layer: database tables, analytics CLI, and worker job
`scores`. The dashboard and chain detail consume these results through the
public API. Methodology and Legal are statically generated for English and
Persian, with all user-facing copy in `frontend/messages/en.json` and
`frontend/messages/fa.json`. The Methodology page reads pillar weights from the
public methodology endpoint and uses a documented static fallback; the shared
data-attribution footer provides full public-site and compact app variants.
The backend agent API, provider interface, allow-listed read-only tools,
grounding checks, bilingual guardrails, and offline evaluation harness are
implemented, along with a bilingual user-facing chat UI. Watchlist and alert
backend functionality is implemented; its frontend and delivery remain
planned. Additional public SEO and learning pages are deferred to Prompt 15.

Public data routes are GET-only and unauthenticated. They expose chain
snapshots, score history, reported regimes, risk flags, methodology, and
allow-listed raw series and historical-return scenarios. Decimal values
serialize as strings; unavailable and context-only series carry explicit
status/role metadata. Public responses are cached for five minutes and use an
in-process per-IP rate limiter. No CORS settings were added for this API;
development remains same-origin through the Next.js rewrite.

### Frontend public data layer

The browser uses the same-origin `/api/v1` client, strict Zod response
contracts, and shared TanStack Query keys. Query data stays fresh for five
minutes, does not refetch on window focus, and deduplicates requests for the
same key. Public API errors are converted to localized messages, including a
safe `Retry-After` duration for rate limits.

API decimal values remain strings through contracts and query caching.
Conversion to JavaScript numbers happens only when formatting a visible value
or building chart coordinates. Score history ranges use UTC dates; the chart
is dynamically loaded, uses a fixed 0–100 axis, and inserts null values for
missing calendar dates so gaps remain gaps. The chart legend can hide
individual chains, and its caveat explains that scores use different inputs
and are relative to each chain's own history.

The chains screener reuses the same chain query and score presentation. Its
sortable columns and filters operate on the API's Decimal strings, and
allow-listed filter state is reflected in the URL.

The chain detail route validates the slug before querying and uses separate
TanStack Query keys for the snapshot, score history, regimes, price series,
scenarios, and methodology. Each section owns its loading, empty, retryable
error, and resolved states, so one failed endpoint does not hide the rest of the
page. Pillar and component weights come from methodology; component
percentiles are shown when present, and values unavailable for a chain are
identified rather than inferred. The score-history and price charts
load Recharts through a client-side dynamic chunk, plot Decimal strings only
after converting at the chart boundary, and keep missing dates as null gaps.
The history range is UTC-based (1Y, 3Y, or up to 3650 days). The regime
timeline keeps source periods ordered and merges only contiguous runs with the
same label.

The scenario engine uses Binance close-to-close returns from exact calendar-day
endpoints, with no gap filling or look-ahead. Its public results are historical
quantiles, not forecasts. The detail page shows the pessimistic, base, and
optimistic quantiles with independent sample counts and low-sample context;
scenario values use neutral styling rather than price-return colors. The
365-day card notes that calibration could not be assessed with too few
independent windows. Dashboard, screener, and chain-detail score notes link to
the Health Score methodology; the scenario note links to the scenario method.

### Agent chat UI

The chat client sends authenticated POST requests through the same-origin
`/api` rewrite and parses SSE from a `ReadableStream`; `fetch` is used because
the request includes a message body and supports the existing bearer-token
refresh flow and `AbortController`. The active conversation UUID is kept in
the `c` URL search parameter, not browser storage. The UI waits for the
backend's verification to finish before displaying answer tokens. Conversation
titles, tool summaries, and assistant text are untrusted and render only as
plain React text; the client does not parse HTML or Markdown.

Planned, not implemented: alert frontend and external delivery, and additional
public SEO and learning pages. The agent backend is
authenticated and tool-limited; conversations are stored and sent to the
configured provider. See [AGENT.md](AGENT.md) for its data flow, grounding
checks, and operational limits.

## Auth

Passwords are hashed with Argon2id. Login returns a short-lived signed JWT
access token in the response; clients should keep it in memory rather than
persistent browser storage. A cryptographically random opaque refresh token is
stored only as a SHA-256 hash in PostgreSQL and delivered in an httpOnly,
SameSite=Lax cookie scoped to `/api/v1/auth`. Cookie `Secure` and optional
domain attributes are configurable for deployment.

Login and refresh also issue a readable CSRF cookie at path `/`; the refresh
cookie remains scoped to `/api/v1/auth`. Refresh and logout require the matching
`X-CSRF-Token` header and reject a mismatched `Origin` when one is provided.
Each refresh rotates the token and revokes its predecessor; reuse of a revoked
token revokes every active token in that family. Logout revokes the current
refresh token and clears both cookies.

Verification and password-reset links use single-use SHA-256-hashed email
tokens; verification links expire after 24 hours and password-reset links after
one hour. A new reset request invalidates earlier unused reset tokens. Email is
queued with FastAPI background tasks. Development uses a console/file sender
that writes under `backend/.dev-mail`; non-development environments require
SMTP configuration. Delivery failures are logged by exception type only, never
with recipient addresses or tokens.

Five consecutive failed logins lock an account for 15 minutes. A locked login
returns the same generic invalid-credentials response and does not verify the
password. In-process sliding-window limits are 10 login attempts per minute per
IP and 5 per minute per email; registration is 5 per hour per IP; password
recovery and verification resend are 10 per hour per IP and 5 per hour per
email. The per-email login limit counts attempts, while account lockout counts
failed passwords: a successful login does not increase the failed-password
counter, but it does consume a rate-limit attempt. Rate limiting is checked
before the locked-account response so known and unknown emails receive the same
429 threshold. After the rate-limit window expires, a locked account still
receives the generic invalid-credentials response. Five failed attempts can
temporarily lock a victim account; the per-IP limit constrains attempts from
any one source but does not eliminate this denial-of-login risk. `X-Forwarded-For`
is ignored unless `TRUST_PROXY=true`. The limiter is per-process; a multi-worker
deployment will need a shared store such as Redis.

Google sign-in uses OpenID Connect with state and nonce in a short-lived signed
httpOnly cookie and PKCE. The callback validates the ID-token signature,
issuer, audience, expiry, and nonce against Google's JWKS. Only a Google
identity with `email_verified=true` may be linked by email or create a verified
passwordless account. Automated tests mock token exchange; real Google login
has not been verified. Real SMTP delivery has also not been verified.

The frontend forwards same-origin `/api/:path*` requests to `BACKEND_URL`
(default `http://127.0.0.1:8010`). Open the app at `http://localhost:3000` so
the browser Origin matches `FRONTEND_ORIGIN`. Access tokens exist only in
frontend memory; the readable CSRF cookie is used to bootstrap/rotate the
refresh session. Login, registration, forgot/reset password, email
verification, Google callback, and security settings are bilingual. Token
pages immediately remove query tokens from the address bar and use
`Referrer-Policy: no-referrer` and `Cache-Control: no-store`. The callback
restores the session through the refresh endpoint; login notices accept only
explicitly whitelisted query values.

The security settings page displays the account email and verification status
and supports password changes. The backend revokes other refresh-token
families while preserving the current family, so the current session remains
valid without refreshing its access token. A client-side app layout guard
provides loading and redirect UX, but it is not an authorization boundary: the
API must enforce authentication and roles on every protected endpoint.

Real SMTP delivery and a live Google OAuth login have not been verified.

## Agent API

The authenticated agent API stores user-scoped conversations and serves
messages with server-sent events. A provider interface supports a disabled
default, a scripted fake, and an OpenAI-compatible implementation. Its
allowlisted tools call the same read-only services as the public API; tools
cannot access account data or write application records. Input classification
can return a deterministic bilingual refusal without contacting a provider.

The orchestrator treats prompts and tool results as untrusted, caps tool calls
and total time, and verifies the completed response's numbers and wording
before streaming any text. One revision is attempted after a failed check;
otherwise a structured projection of retrieved data is returned with a
failure status. Conversation messages and tool results are persisted, while
usage rows contain provider/model and token/latency metadata only. Messages
are sent to the configured provider. The bilingual UI discloses this storage
and provider flow before the composer; no live-model evaluation has been run.
See [AGENT.md](AGENT.md) for detailed behavior and the offline evaluator.

## Data layer

The database contains `chains`, `data_sources`, `metric_definitions`,
`observations`, `series_coverage`, `ingestion_runs`, `rpc_probes`, `features`,
`health_scores`, `regimes`, `risk_flags`, `watchlist_items`, `alert_rules`, and
`alert_events`, in addition to the auth and agent tables. Agent storage
includes conversations, messages, and metadata-only language-model usage.
Observations use a composite
primary key of chain, metric, source, and UTC observation date. Values are
PostgreSQL `NUMERIC(38,12)` values, never floating point.

Providers implement `MetricProvider.fetch(chain, metric, start_date, end_date)`
and return `Point(date, Decimal)`. The shared HTTP client uses a ChainCompass
User-Agent, timeouts, bounded retries, exponential backoff with jitter,
`Retry-After` handling, and a configurable per-provider minimum interval.
A 429 stops the provider for that ingestion run.

Rows are validated before upsert: finite, non-negative values that fit
`NUMERIC(38,12)`, dates not in the future, and no same-day duplicates. Extra
source decimal places are rounded to the database's 12-place scale using
`Decimal`; today's incomplete UTC day is never stored. PostgreSQL
`INSERT ... ON CONFLICT DO UPDATE` makes reruns idempotent, and writes are
batched. Incremental runs overlap the last three days by default; Coin Metrics
uses a seven-day overlap for revised on-chain observations.

Coverage is recomputed after each run. Prices and volumes become stale after
two UTC days; on-chain, fees, TVL, stablecoin, and network metrics use a
three-day threshold. Any successfully fetched series whose last point is older
than the configurable `INGESTION_DISCONTINUED_DAYS` threshold (default 30 days)
is `discontinued`, not `stale`. Missing days remain gaps; providers never
forward-fill or interpolate. `series_coverage` distinguishes `ok`, `stale`,
`error`, `never_run`, `unavailable` (verified HTTP 403/404 or documented
absence), and `discontinued`. Runs record success/rejection counts and
truncated errors.

The providers currently ingest Binance daily klines, Coin Metrics Community
daily market-cap/on-chain metrics, DefiLlama TVL/stablecoin plus chain-level
DEX-volume and protocol-fee histories, and Blockchain.info BTC hashrate and
fees. The metric definitions include `dex_volume_usd` and
`protocol_fees_usd`; the latter is fees paid to protocols, not network/base
transaction fees. DefiLlama's chart response does not declare a unit, so the
USD suffix is a schema convention and the raw unit remains unverified. These
two metrics are admitted only when complete-day values parse as `Decimal`,
span at least 365 days, and the latest point is at most three days old. Gaps
remain visible and are never filled. Binance `USDT` pairs are a USD proxy for
close and quote-volume metrics, not an independent fiat-USD measurement.
Blockchain.info reports hashrate in TH/s, converted to H/s by multiplying by
10^12. Its transaction-fees chart is BTC-denominated; daily fees are converted
to USD with the matching Binance BTC close and remain stored under the
Blockchain.info fee source as a derived series. The 228 historical fee-chart
rows without a same-day Binance close are intentionally omitted. Chart
response spans are limited, so the provider fetches sequential bounded windows.
The legacy Coin Metrics `bnb` asset ended on 2019-04-22 and is not BNB Chain;
those observations are excluded from updates and can be removed only through
the explicit, confirmed `python -m app.ingest purge --provider coinmetrics
--chains bnb --yes` command. The purge is recorded in `ingestion_runs`.

The `check` command flags day-over-day moves only for price, market cap, TVL,
and stablecoin supply (40% by default, configurable with `--jump-threshold`).
Volume, transactions, and active addresses are compared with their trailing
30-day median; a zero median or at least 10 zero observations in the window is
reported once per sparse series and suppresses its outlier alert. Leading zero
runs are reported as informational pre-launch zeros.

Coin Metrics Community requires attribution and is non-commercial. Preserve
attribution for DefiLlama, Blockchain.info, and mempool.space, and review each
source's current terms before redistribution. Availability differs by asset;
HTTP 403/404 responses are recorded as `unavailable`, not as successful empty
series.

## Worker process

Run the ingestion scheduler as a separate process with
`python -m app.worker`; it does not share the API process and requires no
Redis. The implemented APScheduler jobs are:

- `coingecko_snapshot`: daily at 00:05 UTC.
- `update_all`: daily at 00:30 UTC.
- `rpc_probe`: every 15 minutes.
- `prune_rpc_probes`: daily at 00:45 UTC.
- `scores`: daily at 01:00 UTC; updates features, then computes scores,
  regimes, and flags.
- `alerts_eval`: daily at 01:15 UTC; evaluates active alert rules after scores.

Jobs use one instance per
scheduler, coalesce missed invocations, allow a one-hour misfire grace period,
and include up to 20 seconds of jitter. `update_all` calls the existing
`app.ingest update --all` path rather than duplicating provider logic.

`alerts_eval` checks the latest complete stored score/regime date and at most
three earlier calendar dates. It requires the exact previous date for each
comparison and does not fill gaps. Events use a unique rule/date key so job
retries do not add duplicates; one invalid rule does not stop evaluation of
other rules.

Before running a job, the worker takes a non-blocking PostgreSQL advisory lock
keyed by job name. A duplicate process logs `skipped: already running` and
does not create a run record or write data. Each acquired invocation is tracked
in `ingestion_runs`; failure, including a handled CoinGecko rate limit, is
recorded without stopping the scheduler. SIGINT/SIGTERM request shutdown where
the platform supports signal handlers; Ctrl+C is handled on Windows.

The CoinGecko job makes one `/api/v3/coins/markets` request for BTC, ETH, SOL,
and BNB. `COINGECKO_API_KEY` is optional. It stores positive finite
`Decimal` market caps under the separate `coingecko` source; it does not
backfill history or overwrite Coin Metrics rows. The daily run is scheduled
around 00:05 UTC, labels the observation with the previous UTC date, and records
the exact collection timestamp in run details. These are approximate end-of-day
snapshots, collected forward from the first run; missed days remain gaps.
Retries are bounded to three after the initial request, honor `Retry-After`,
and end as `rate_limited` on HTTP 429 or `failed` for other exhausted errors.

The `rpc_probe` job queries BTC, ETH, SOL, and BNB sequentially with one
10-second request timeout and no retry. It records only the provider label,
result, timing, block height/age when available, and a short sanitized error
code; RPC URLs, response bodies, and credentials are not persisted or logged.
BTC uses mempool.space's tip-height endpoint; ETH and BNB use
`eth_getBlockByNumber`; SOL uses `getSlot` followed by `getBlockTime`. A SOL
block-time failure retains the slot with a null age. Individual probe failures
are recorded without aborting the other chains. Small negative block ages up
to 60 seconds are clamped to zero as clock skew; larger negative ages are
invalid. A daily `prune_rpc_probes` job removes rows older than 30 days; probes
can also be pruned manually with `python -m app.ingest prune-probes --days 30`.

The existing user `role` (`user` or `admin`) gates three read-only endpoints:
`GET /api/v1/admin/data-freshness`, `/pipeline`, and `/rpc-health`. Freshness
reports lag and a stale flag using the configured discontinued threshold;
pipeline results include recent runs and per-job/provider last success; RPC
health reports the latest provider result and per-chain 24-hour success and
median latency. `python -m app.users set-role --email <email> --role admin`
grants access without changing credentials. No admin write endpoints or
audit-log feature are included.

## Point-in-time feature layer

The feature engine reads only the explicit chain/metric/source allow-list in
`app.analytics.registry`. It computes daily trailing-window features using
`Decimal`, stores them in `features`, and records each run as job `features`.
Features are keyed by chain/name/as-of date and retain source metric/source
metadata. Context-only inputs are feature-computable but are not score eligible; score
code consults the registry rather than inferring eligibility from names.

Every as-of calculation is causal: exact return endpoints, daily log-return
windows, medians, drawdowns, and moving averages use only rows dated at or
before the as-of date. Gaps are omitted, coverage thresholds control whether a
value exists, and no values are filled. A 30-day non-zero run confirms a
series' effective start only on its 30th day; earlier features are not
retroactively emitted. Values are rounded to 12 decimal places with Decimal
arithmetic. See [FEATURES.md](FEATURES.md) for formulas, coverage rules, and
registry roles.

## Health Score, regimes, and risk flags

The deterministic, point-in-time `v1` scoring layer uses only score-role inputs
from the feature registry. It stores chain-relative percentile scores with
coverage/confidence, price-based regimes with five-day hysteresis, and
threshold-based risk flags. Percentile history availability limits early score
dates. See [HEALTH_SCORE.md](HEALTH_SCORE.md) for the fixed weights, thresholds,
confidence limits, calculations, and limitations. These outputs are analysis,
not advice or predictions.

DefiLlama chain-level DEX volume for ETH, SOL, and BNB is only a low-weight
Health Score candidate pending unit and methodology validation. BTC DEX volume
is context-only because the measured breakdown is dominated by LN Exchange
Spot and Bisq. Protocol-fee totals for every chain are context-only and never
enter the Health Score: they aggregate ecosystem protocol activity rather than
base/network fees or chain usage. The 208 observed trailing-median alerts are
informational; changes in listed protocol composition are a possible, not
proven, explanation. Score inputs should use robust medians/quantiles.
CoinGecko market-cap snapshots are used only for cross-checks/context, never as
score inputs; a manual mid-day snapshot is intraday data labeled with the
previous UTC date.

## Key decisions

- **Monorepo:** frontend, API, worker, infrastructure, and shared product
  documentation evolve together; one repository makes local setup and
  cross-component changes easier to review.
- **No Redis in phase 1:** a separate APScheduler process is sufficient for the
  initial workload and avoids operating an additional service before needed.
- **Rule-based score v1:** fixed, documented percentiles and weights make the
  first Health Score reproducible and explainable before considering more
  complex scoring approaches.
- **Planned historical-quantile scenarios:** use return distributions to
  communicate ranges and uncertainty, not point predictions or claims of
  predictive accuracy.
- **Tokens in memory + httpOnly refresh cookie:** keep access tokens out of
  persistent browser storage; protect the rotating refresh token from
  JavaScript access with an httpOnly cookie.
