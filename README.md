# ChainCompass

Bilingual foundation for an on-chain intelligence app for long-term crypto investors.

## Status: early development (auth foundation implemented)

**Disclaimer:** ChainCompass is for informational purposes only, is not financial advice, and does not provide buy or sell recommendations.

See [Windows setup](docs/SETUP.md) to prepare the development environment.

## Implemented

- Bilingual English/Persian routing with right-to-left layout for Persian.
- Dark and light themes.
- Public landing page.
- FastAPI health endpoint.
- PostgreSQL connection and health checks.
- GitHub Actions CI workflow for frontend, backend, and secret scanning.
- Auth core: registration, login, short-lived JWT access tokens, rotating
  refresh-token cookies, CSRF checks, logout, and authenticated `/me`.
- Email verification and password recovery flows, login lockout, and
  per-process rate limiting.
- Google OpenID Connect flow with PKCE and verified-email linking rules.

## Planned

- On-chain data ingestion and analysis for BTC, ETH, SOL, and BNB.
- Network Health Score and capital-flow analysis.
- Historical-distribution scenarios.
- Risk alerts and watchlists.
- Tool-grounded AI analyst.
- Administrative tools.

**Not verified:** Real SMTP delivery and a live Google OAuth login have not
been exercised; Google callback/token exchange is covered with mocked tests.

## Architecture

See the [architecture overview](docs/ARCHITECTURE.md).

## Getting Started

See [Windows setup](docs/SETUP.md) for native PostgreSQL (recommended) and
optional Docker setup. For PostgreSQL running natively, first copy `.env.example`
to `.env`, then set matching local database credentials:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
Set-Location backend
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Docker is optional. To use the PostgreSQL container instead, run from the
repository root (connect to a trusted VPN first if Docker Hub is unreachable):

```powershell
docker compose --env-file .env -f infra/docker-compose.yml up -d
```

## Native PostgreSQL on Windows

PostgreSQL 16 can run natively; Docker is optional. Install it from
[postgresql.org](https://www.postgresql.org/download/windows/) and install the
Microsoft Visual C++ Redistributable 2015–2022 (x64). If PostgreSQL's `bin`
folder is not in `PATH`, use its full path:

```powershell
$pgBin = 'C:\Program Files\PostgreSQL\16\bin'
Get-Service postgresql*
& "$pgBin\pg_isready.exe" -h localhost -p 5432
```

In an interactive session, connect as the `postgres` superuser, create the
project role and database, and set the role password with `\password` (choose a
letters-and-digits-only password; do not put it in command history):

```powershell
& "$pgBin\psql.exe" -W -U postgres -h localhost -d postgres
```

```sql
CREATE ROLE chaincompass LOGIN;
\password chaincompass
CREATE DATABASE chaincompass OWNER chaincompass;
\connect chaincompass
GRANT USAGE, CREATE ON SCHEMA public TO chaincompass;
\quit
```

Set matching local-only values in the ignored root `.env`:

```dotenv
DATABASE_URL=postgresql+asyncpg://chaincompass:YOUR_LETTERS_AND_DIGITS_PASSWORD@localhost:5432/chaincompass
POSTGRES_USER=chaincompass
POSTGRES_PASSWORD=YOUR_LETTERS_AND_DIGITS_PASSWORD
POSTGRES_DB=chaincompass
```

If `postgres.exe` exits with `-1073741515`, the Visual C++ runtime is missing.

In another PowerShell window, start the frontend from its directory:

```powershell
Set-Location frontend
npm ci
npm run dev
```

See the [Windows setup guide](docs/SETUP.md) for the full sequence and verification commands.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| Foundation | Repository, bilingual frontend foundation, landing page, backend health scaffold, database connectivity, and CI configuration | Done |
| Phase 1 | Authentication and core chain analysis, watchlists, alerts, and chat agent | In progress; core product features are planned |
| Phase 2 | Level-2 protocol coverage, dedicated capital flows and risk center, comparison, plans/waitlist, and learning resources | Planned |

## Documentation

- [Product requirements](docs/PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Setup guide](docs/SETUP.md)
- [Data audit](docs/DATA_AUDIT.md)
- [Learning log](docs/LEARNING_LOG.md)

## Disclaimer

Not financial advice. ChainCompass provides informational analysis only and does not give buy or sell recommendations.
