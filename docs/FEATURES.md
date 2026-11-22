# Point-in-time feature layer

This layer creates descriptive daily measurements for later Health Score,
regime, risk-flag, scenario, and walk-forward work. It does not make
predictions or provide financial advice. It is designed to avoid look-ahead:
the feature value at `as_of_date = t` uses only registered observations whose
`obs_date <= t`.

## Input registry

Only the following chain/metric/source combinations are read. The registry in
`backend/app/analytics/registry.py` is the code allow-list and is the source of
truth for score eligibility. `context` features are stored for analysis but
must never be treated as Health Score inputs.

| Inputs | Chains | Source | Role |
|---|---|---|---|
| `price_close_usd`, `volume_usd` | BTC, ETH, SOL, BNB | Binance | score |
| `active_addresses`, `tx_count` | BTC, ETH | Coin Metrics Community | score |
| `market_cap_usd` | BTC, ETH | Coin Metrics Community | context |
| `tvl_usd`, `stablecoin_supply_usd`, `dex_volume_usd` | ETH, SOL, BNB | DefiLlama | score |
| `hashrate` | BTC | Blockchain.info | score |
| `fees_usd` | BTC | Blockchain.info-derived, converted using same-day Binance close | score |
| `protocol_fees_usd` | BTC, ETH, SOL, BNB | DefiLlama | context |
| `dex_volume_usd` | BTC | DefiLlama | context |
| `market_cap_usd` | BTC, ETH, SOL, BNB | CoinGecko snapshots | context |

Unavailable and discontinued combinations are deliberately absent: legacy BNB
and SOL Coin Metrics on-chain metrics, and BTC DefiLlama TVL/stablecoin supply.
The CoinGecko market-cap feature names are prefixed
`coingecko_market_cap_usd_` to distinguish them from Coin Metrics market cap.
DefiLlama units remain unverified; its protocol fees are not network fees.

## Catalog and calculation rules

All windows are trailing calendar days, inclusive of `t`, unless an exact
calendar offset is specified. Gaps remain missing; observations are never
forward-filled or interpolated. A window that misses its coverage threshold
produces no feature.

| Feature | Formula | Window and coverage | Inputs / role |
|---|---|---|---|
| `ret_7d`, `ret_30d`, `ret_90d`, `ret_365d` | `close(t) / close(t-N) - 1` | Exact observations at both endpoints; `N` calendar days | Binance `price_close_usd`, all chains; score |
| `realized_vol_30d`, `realized_vol_90d` | Sample standard deviation (`ddof=1`) of daily log returns, multiplied by `sqrt(365)` | 30/90 daily returns; at least 27/81 valid returns; the first return also requires its prior close | Binance `price_close_usd`, all chains; score |
| `drawdown_365d` | `close(t) / max(close(d)) - 1`, for `d` from `t-364` through `t`, inclusive | 365 closes including `t`; at least 329 observations and a close at `t` | Binance `price_close_usd`, all chains; score |
| `price_vs_sma200` | `close(t) / mean(close(d)) - 1`, for `d` from `t-199` through `t`, inclusive | 200 closes including `t`; at least 180 observations and a close at `t` | Binance `price_close_usd`, all chains; score |
| `volume_med30` | Median of `volume_usd` | 30 days including `t`; at least 24 observations | Binance `volume_usd`, all chains; score |
| `volume_ratio_30_365` | 30-day median divided by 365-day median | Numerator requires 24/30; denominator requires 329/365 and must be positive | Binance `volume_usd`, all chains; score |
| `<metric>_med30` | Median of the registered metric | 30 days including `t`; at least 24 observations | All registered level metrics; role inherited from registry |
| `<metric>_chg30` | `med30(t) / med30(t-30) - 1` | Both 30-day medians must exist; denominator positive; total span 60 days | All registered level metrics; role inherited from registry |
| `<metric>_chg90` | `med30(t) / med30(t-90) - 1` | Both 30-day medians must exist; denominator positive; total span 120 days | All registered level metrics; role inherited from registry |

`n_obs` counts distinct raw observations used by a feature. For volatility,
which consumes daily returns, it counts the unique closes backing the valid
returns. Change features count the union of observations used by the two
medians. `window_days` records the feature window (or the full combined span
for change features).

## Effective start and point-in-time behavior

For each registered series, the effective start is the first date of its first
run of 30 consecutive calendar days with non-zero observations. A missing day
or a zero breaks a run. Values dated before that start are excluded, and a
feature window may not reach before it. The exclusion is logged once per series.

The run is confirmed only after its 30th observation is available. Therefore,
features for dates before that confirmation are not retroactively created.
This avoids letting later observations determine whether an earlier date was
eligible. The engine advances in date order and confirms eligibility using
only observations available through each `as_of_date`; appending or changing
future observations cannot change earlier feature rows.

## Precision and storage

Calculations and outputs use `Decimal` only; no binary floating point is used.
Every stored feature is quantized to 12 decimal places using
`ROUND_HALF_EVEN`, matching `NUMERIC(38,12)`. Features are keyed by chain,
feature name, and as-of date, with source metric and source recorded for
traceability. Score eligibility is resolved through the input registry, not
inferred from a feature name.

The CLI can rebuild all history or recompute the last 14 complete dates:

```powershell
Set-Location backend
& .\.venv\Scripts\python.exe -m app.analytics compute-features --backfill
& .\.venv\Scripts\python.exe -m app.analytics compute-features --backfill --chain btc
& .\.venv\Scripts\python.exe -m app.analytics compute-features --update
& .\.venv\Scripts\python.exe -m app.analytics feature-status
```

Each computation is recorded in `ingestion_runs` as job `features`. The feature
engine is a library and opt-in CLI only; it is not scheduled in the worker.

## Watchlist and alerts

Implemented in the backend: authenticated per-user chain watchlists, validated
regime-change, risk-flag, and score-cross rules, and in-app event storage. The
daily evaluator runs after the score job, uses exact stored consecutive UTC
dates, and writes newly triggered conditions with an idempotent rule/date key.
Events contain stable type codes and structured payloads; Decimal values are
serialized as strings. This feature reports historical conditions and is not
financial advice. Frontend display and email/Telegram delivery are planned.
