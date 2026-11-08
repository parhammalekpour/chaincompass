# Product Requirements

## Vision

ChainCompass is an on-chain intelligence web app for long-term crypto investors,
turning blockchain and market data into clear, evidence-based analysis rather
than financial advice or trading recommendations.

## Target user

Long-term investors who are not on-chain experts and want plain-language,
evidence-based analysis. The product serves both English and Persian speakers,
including Persian readers who need a complete right-to-left experience.

## Scope

Phase 1 covers Bitcoin (BTC), Ethereum (ETH), Solana (SOL), and BNB Chain (BNB).

## Phase 1 pages

### Landing
Introduces the product, supported chains, and trust principles.
Key elements: value proposition, feature overview, freshness cues, sign-in entry, and disclaimer.

### Login
Provides secure email/password and Google sign-in.
Key elements: labeled form, validation, accessible errors, and links to registration and account recovery.

### Register
Creates an account and supports forgot-password, reset-password, and email-verification flows.
Key elements: validated signup form, verification status, recovery links, and clear success/error states.

### Methodology
Explains how chain health, capital-flow analysis, alerts, and scenarios are produced.
Key elements: metric definitions, source notes, scoring limitations, uncertainty, and freshness.

### Legal
Presents terms, privacy information, and the product disclaimer.
Key elements: readable policy content, update dates, and links to related legal pages.

### Dashboard
Gives signed-in users a concise overview of supported-chain health and notable changes.
Key elements: score summaries, watchlist highlights, risk alerts, freshness, and scenario ranges.

### Chains (screener)
Lets users scan and sort the supported chains using consistent metrics.
Key elements: searchable chain list, health indicators, metric summaries, and loading/empty/error states.

### Chain Detail
Shows the evidence and context behind one chain's current health.
Key elements: metric trends, network activity, methodology links, historical context, and data timestamps.

### Chat Agent
Answers questions using approved analysis tools and sourced data only.
Key elements: conversational interface, citations/tool evidence, uncertainty, and explicit limits; the agent states numbers only when returned by tools.

### Watchlist
Lets users keep selected chains close at hand.
Key elements: add/remove chains, current summaries, alert shortcuts, and empty/loading/error states.

### Alerts
Shows relevant risk and network alerts without turning them into trade instructions.
Key elements: severity, explanation, affected chain, observed time, and user notification preferences.

### Settings
Manages account preferences and the bilingual experience.
Key elements: language/direction, profile and security controls, notification settings, and session management.

## Admin

Provide operational views for service health, ingestion pipeline, users, LLM
usage, notifications, agent review, audit log, and feature flags. Restrict access
to authorized administrators and record sensitive administrative actions.

## Phase 2 backlog

- Level-2 protocols per chain.
- Dedicated Capital Flow page.
- Risk Center.
- Chain and metric comparison.
- Plans and waitlist.
- Learn section with educational material.

## Non-goals

- No buy/sell signals.
- No price predictions or point forecasts.
- No payments or subscriptions in phase 1.
- No trading or transaction execution.

## Disclaimer

ChainCompass is for informational and educational purposes only. It is not
financial, investment, or trading advice, and it does not recommend buying,
selling, or holding any asset. Users are responsible for their own decisions.

## Quality bar

Follow the Definition of Done in
[Copilot instructions](../.github/copilot-instructions.md): bilingual EN/FA with
RTL, responsive behavior, loading/empty/error states, typed and tested code,
passing lint and type checks, no console errors, and updated documentation.
