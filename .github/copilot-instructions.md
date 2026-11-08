# ChainCompass: Copilot Instructions

## Product
Bilingual (EN default, FA with full RTL) on-chain intelligence web app for
LONG-TERM investors. Covers BTC, ETH, SOL, BNB. Provides network health scores,
capital-flow analysis, risk alerts, 3-scenario outlooks (from historical return
distributions, never point predictions), and an AI chat agent.
It is NOT financial advice and never gives buy/sell calls.

## Environment
Windows 11, PowerShell. Develop natively on Windows; Docker Desktop only runs
PostgreSQL and Mailpit. All commands in docs/README must work in PowerShell.
User is in Iran: prefer free sources, expect some services to need a VPN, and
make every external provider swappable behind an interface.

## Stack
- Frontend: Next.js (App Router) + TypeScript strict + Tailwind + shadcn/ui,
  next-intl, TanStack Query, Recharts, lightweight-charts, react-hook-form, Zod
- Backend: FastAPI + SQLAlchemy 2 (async) + Alembic + Pydantic v2, PostgreSQL
- Jobs: APScheduler inside a separate worker process (no Redis in phase 1)
- LLM: provider interface (Ollama locally; OpenAI-compatible APIs such as Gemini,
  Groq, OpenRouter). The agent may ONLY state numbers returned by tools.
- Auth: email+password (Argon2) and Google OAuth; short-lived access token,
  refresh token in httpOnly cookie with rotation. Never use localStorage for tokens.
- Frontend and API share one origin in dev via Next.js rewrites (/api -> backend).

## Rules
- Small, reviewable changes. One feature per change. Briefly explain WHY.
- Every user-facing string lives in messages/en.json and messages/fa.json.
  Real Persian translations. No hard-coded text.
- RTL: logical Tailwind classes only (ms-, me-, ps-, pe-, start-, end-,
  text-start). Never ml-, mr-, pl-, pr-, left-, right-. Charts, numbers and code
  stay LTR. Always Latin digits (numberingSystem latn), tabular-nums.
- Every page has Loading (skeleton), Empty and Error states.
- Validate all input (Zod frontend, Pydantic backend).
- No secrets in code. Keep .env.example updated.
- Tests for auth, scoring, ingestion, agent tools, alerts.
- Dark theme default, light supported via CSS-variable design tokens.
- Accessibility: labels, focus states, contrast, keyboard navigation.
- Never claim predictive accuracy. Show uncertainty and data freshness.

## Definition of Done
Works in EN and FA (RTL), responsive, 3 states handled, typed, tested,
lint and typecheck pass, no console errors, docs updated.
