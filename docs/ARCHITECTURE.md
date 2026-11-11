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

Login and refresh also issue a readable CSRF cookie. Refresh and logout require
the matching `X-CSRF-Token` header and reject a mismatched `Origin` when one is
provided. Each refresh rotates the token and revokes its predecessor; reuse of
a revoked token revokes every active token in that family. Logout revokes the
current refresh token and clears both cookies.

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
email. `X-Forwarded-For` is ignored unless `TRUST_PROXY=true`. The limiter is
per-process; a multi-worker deployment will need a shared store such as Redis.

Google sign-in uses OpenID Connect with state and nonce in a short-lived signed
httpOnly cookie and PKCE. The callback validates the ID-token signature,
issuer, audience, expiry, and nonce against Google's JWKS. Only a Google
identity with `email_verified=true` may be linked by email or create a verified
passwordless account. Automated tests mock token exchange; real Google login
has not been verified. Real SMTP delivery has also not been verified.

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
