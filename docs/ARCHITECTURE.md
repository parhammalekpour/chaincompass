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
                   | PostgreSQL  |    | LLM provider interface  |
                   +-----^------+    | Ollama / OpenAI-compatible|
                         |           +--------------------------+
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

       FastAPI / Worker ---> Notifiers: Email SMTP, Telegram
```

The browser and API share one development origin: Next.js forwards `/api` to
FastAPI. FastAPI serves validated application requests and reads/writes
PostgreSQL. A separate APScheduler worker collects and normalizes data from
swappable external providers before storing it. The API calls language models
through a provider interface, and notification adapters deliver email or
Telegram messages.

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

## Data layer

The ingestion data model consists of `chains`, `data_sources`,
`metric_definitions`, `observations`, `series_coverage`, and `ingestion_runs`.
Observations use a composite primary key of chain, metric, source, and UTC
observation date. Values are PostgreSQL `NUMERIC(38,12)` values, never floating
point.

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
30-day median; leading zero runs are reported as informational pre-launch zeros.

Coin Metrics Community requires attribution and is non-commercial. Preserve
attribution for DefiLlama, Blockchain.info, and mempool.space, and review each
source's current terms before redistribution. Availability differs by asset;
HTTP 403/404 responses are recorded as `unavailable`, not as successful empty
series.

## Key decisions

- **Monorepo:** frontend, API, worker, infrastructure, and shared product
  documentation evolve together; one repository makes local setup and
  cross-component changes easier to review.
- **No Redis in phase 1:** a separate APScheduler process is sufficient for the
  initial workload and avoids operating an additional service before needed.
- **Rule-based score first:** transparent, explainable rules provide a
  reproducible baseline before considering more complex scoring approaches.
- **Historical-quantile scenarios:** use return distributions to communicate
  ranges and uncertainty, not point predictions or claims of predictive accuracy.
- **Tokens in memory + httpOnly refresh cookie:** keep access tokens out of
  persistent browser storage; protect the rotating refresh token from
  JavaScript access with an httpOnly cookie.
