# Learning Log

Record each implementation step, a problem or lesson, and its fix for future
review and interview preparation.

| Date | Step | What was built | Problem/lesson and fix |
|---|---|---|---|
| 2026-11-08 | Step 0: foundation | Repository instructions, Windows setup script, and initial project files | A clear scope and toolchain make later decisions easier to validate. |
| 2026-11-08 | Step 1: frontend scaffold | Next.js app foundation, TypeScript, locale routing, theme tokens, and formatting utilities | Node 18 did not meet the Next.js requirement; installing Node 22 and reopening terminals resolved it. |
| 2026-11-08 | Step 2: layouts and landing | Marketing/auth/app shells, navigation, language switcher, page states, and landing page | Reusable layouts keep navigation and shared UI consistent across pages. |
| 2026-11-09 | Step 3: backend and CI | FastAPI health API, async database session, Alembic baseline, tests, PostgreSQL configuration, and CI workflow | Docker Hub pulls stalled, so PostgreSQL was run natively on Windows instead. |
| 2026-11-11 | Step 4: locale verification | Explicit locale propagation for the landing page and footer, with production-render checks | Marketing text stayed English on `/fa`; passing the locale explicitly fixed it, then rendered EN/FA output was verified. |
| 2026-11-11 | Native PostgreSQL on Windows | Verified the PostgreSQL 16 service, project role/database, migration, and API health behavior | Exit code `-1073741515` indicated a missing Visual C++ Redistributable; installing the x64 runtime fixed startup. An unrelated process held port 8000, so the API ran temporarily on 8010. |
| 2026-11-19 | Prompt 7: free data source audit | Audited no-key public APIs from Iran with VPN and bounded requests | CoinGecko and Binance supplied measured 365-day BTC/ETH/SOL/BNB market history; DefiLlama supplied measured chain TVL and stablecoin histories; Coin Metrics community timeseries returned HTTP 400 for the tested metrics, while its catalog reached 200. CoinGecko stopped BNB chart probing after HTTP 429 with Retry-After 60. The free market/RPC sources can be used where measured, but unsupported on-chain active-address, transaction, fee, TVL, stablecoin, and validator components must remain unavailable rather than estimated. |
