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
current refresh token and clears both cookies. User lockout fields are present,
but lockout enforcement and rate limiting are deferred to auth step 5B.

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
