# Network Health Score, Regimes, and Risk Flags

This versioned analysis layer is deterministic and point-in-time. It describes
historical on-chain and market conditions; it is **not financial advice**, a
buy/sell recommendation, or a prediction. No threshold or weight is tuned from
the current database run or from future returns.

## Version and inputs

The fixed policy is `v1`, defined in
[`backend/app/analytics/score_config.py`](../backend/app/analytics/score_config.py).
Only score-role metric/source pairs in
[`backend/app/analytics/registry.py`](../backend/app/analytics/registry.py)
can contribute. Context-only and unavailable series are excluded, including
market capitalization, protocol fees, BTC DEX volume, and CoinGecko snapshots.

The engine consumes these existing feature names:

| Pillar | Feature | Chains | Weight | Direction |
|---|---|---|---:|---|
| Adoption | `active_addresses_chg90` | BTC, ETH | 15 | Higher |
| Adoption | `tx_count_chg90` | BTC, ETH | 15 | Higher |
| Capital | `tvl_usd_chg90` | ETH, SOL, BNB | 12 | Higher |
| Capital | `stablecoin_supply_usd_chg90` | ETH, SOL, BNB | 12 | Higher |
| Capital | `dex_volume_usd_chg90` | ETH, SOL, BNB | 6 | Higher |
| Security & economics | `hashrate_chg90` | BTC | 7 | Higher |
| Security & economics | `fees_usd_chg90` | BTC | 3 | Higher |
| Market condition | `drawdown_365d` | All | 10 | Higher (closer to zero) |
| Market condition | `realized_vol_90d` | All | 7 | Lower |
| Market condition | `volume_ratio_30_365` | All | 8 | Higher |
| Market condition | `price_vs_sma200` | All | 5 | Higher |

`fees_usd_chg90` is a derived BTC series: Blockchain.info fee amounts converted
using the same-day Binance BTC close. It is labeled as derived in each stored
component. All component feature names above match the existing feature table;
no aliases are needed.

## Component percentile and score

For each feature and date `t`, rank the current value among real feature rows
dated from `t - 1094 days` through `t`, inclusive. The mid-rank percentile is
`(count_less + 0.5 * count_equal) / N * 100`; it is unavailable until at least
365 observations exist. Higher-is-better retains this percentile; lower-is-
better uses `100 - percentile`. Missing dates are not filled.

Within each pillar, available components are averaged using their nominal
weights and the available weights are re-normalized. Missing components
therefore lower coverage without being imputed. Available pillar scores are
combined by their nominal pillar weights, re-normalized over available pillars,
then rounded to two decimal places. A score row is omitted below 0.40 coverage.

Coverage is the sum of available component weights divided by 100. Confidence is
High at coverage `>= 0.80`, Medium at `>= 0.50`, and Low otherwise. Registry-
derived maximum coverage is BTC `0.70`, ETH `0.90`, SOL `0.60`, and BNB `0.60`.
Therefore only ETH can reach High confidence; BTC, SOL, and BNB can reach at
most Medium confidence. This is intentional and reflects their smaller free
on-chain input sets. Confidence is always stored beside the score.

Scores are relative to each chain's own trailing history and use different
component sets across chains. Cross-chain comparisons are indicative only.
Percentiles need at least 365 dated observations, including the current value,
for each component. Score histories therefore begin later than their raw
feature histories; late starts are expected.

## Pillars

| Pillar | Nominal weight |
|---|---:|
| Adoption | 30 |
| Capital | 30 |
| Security & economics | 10 |
| Market condition | 30 |

The pillar JSON records each score, available component weight, and availability.
The component JSON records feature, raw value, percentile, nominal weight, and
direction. Decimal numbers are serialized as decimal strings in JSON to avoid
binary floating-point conversion.

## Market regimes

Raw regimes use only the price-derived features on each date, in priority order:

1. `stress`: `drawdown_365d <= -0.50`.
2. `uptrend`: `price_vs_sma200 > 0` and `ret_90d > 0`.
3. `downtrend`: `price_vs_sma200 < 0` and `ret_90d < 0`.
4. `range`: otherwise, including cases where the required trend inputs are
   unavailable.

The first computed raw regime initializes the reported regime immediately;
`days_in_regime` starts at 1. Thereafter, a different raw label must persist
for five consecutive calendar dates with computed regime inputs before the
reported label changes. A gap resets the consecutive-day counter; it does not
fill or infer a missing regime. `days_in_regime` counts consecutive computed
dates since the reported label began or the last gap.

The volatility overlay ranks `realized_vol_90d` by the same trailing percentile
rule. It is `high` at percentile `>= 80`, `low` at `<= 20`, otherwise `normal`;
it is null until the percentile is available.

## Risk flags

Only true flags are stored. Each stores the observed decimal value, fixed
threshold, severity, date, and version.

| Flag | Condition | Severity |
|---|---|---|
| `deep_drawdown` | `drawdown_365d <= -0.40` | Medium; High at `<= -0.60` |
| `high_volatility` | `realized_vol_30d` percentile `>= 90` | Medium |
| `liquidity_drying` | `volume_ratio_30_365 < 0.50` | Medium |
| `usage_decline` | `active_addresses_chg90 <= -0.20` | Medium; BTC/ETH |
| `tvl_outflow` | `tvl_usd_chg90 <= -0.25` | Medium; ETH/SOL/BNB |
| `stablecoin_contraction` | `stablecoin_supply_usd_chg90 <= -0.10` | Medium; ETH/SOL/BNB |
| `hashrate_decline` | `hashrate_chg90 <= -0.15` | Medium; BTC |
| `low_confidence` | coverage `< 0.50` | Info |

Flags are evaluated only when their input exists, except `low_confidence`, which
uses the calculated coverage. It can be present on dates without a score row.
These are descriptive alerts, not recommendations.

## Storage and commands

`health_scores`, `regimes`, and `risk_flags` are keyed by chain, date, and
version (plus flag for `risk_flags`). Re-running a version replaces its target
rows idempotently; previous versions remain available.

```powershell
Set-Location backend
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m app.analytics compute-scores --backfill
& .\.venv\Scripts\python.exe -m app.analytics compute-scores --backfill --chain btc
& .\.venv\Scripts\python.exe -m app.analytics compute-scores --update
& .\.venv\Scripts\python.exe -m app.analytics score-status
```

Backfill computes all dates available in the materialized feature table.
Update replaces the last 14 complete dates and reads the full past feature
history so the percentile windows and regime hysteresis have their required
lookback. The daily `scores` worker job at 01:00 UTC first updates features and
then scores; its scheduler lock, one-instance limit, coalescing, jitter, and
failure isolation follow the existing worker conventions.
