# ChainCompass

On-chain intelligence for long-term crypto investors, with transparent data and scenario-based outlooks.

**Status:** Frontend scaffold and backend foundation are under active development.

**Disclaimer:** ChainCompass is for informational purposes only, is not financial advice, and does not provide buy or sell recommendations.

See [Windows setup](docs/SETUP.md) to prepare the development environment.

## Features

- Evidence-based on-chain health and capital-flow analysis for BTC, ETH, SOL, and BNB.
- Bilingual English and Persian experience with full right-to-left support.
- Risk alerts and historical-distribution scenarios, with data freshness and uncertainty.

## Architecture

See the [architecture overview](docs/ARCHITECTURE.md).

## Getting Started

Run these commands from the repository root in PowerShell. If Docker Hub is
unreachable or slow, connect to a trusted VPN before pulling the PostgreSQL image.
Before the first startup, replace the database and JWT placeholders in `.env`
with local-only values and keep the database URL credentials matched to the
PostgreSQL variables.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose --env-file .env -f infra/docker-compose.yml up -d
Set-Location backend
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

In another PowerShell window, start the frontend from its directory:

```powershell
Set-Location frontend
npm ci
npm run dev
```

See the [Windows setup guide](docs/SETUP.md) for the full sequence and verification commands.

## Roadmap

- **Phase 1:** Foundation, core chain analysis, watchlists, alerts, and the chat agent.
- **Phase 2:** Level-2 protocol coverage, capital flows, risk center, comparison, plans/waitlist, and learning resources.

## Documentation

- [Product requirements](docs/PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Setup guide](docs/SETUP.md)
- [Data audit](docs/DATA_AUDIT.md)
- [Learning log](docs/LEARNING_LOG.md)

## Disclaimer

Not financial advice. ChainCompass provides informational analysis only and does not give buy or sell recommendations.
