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

## Known behaviours

### Regime confirmation lag

The reported regime waits for five consecutive daily raw labels before it
changes. This intentionally delays regime changes after abrupt moves. In the
stored March 2020 data, BTC and ETH both had raw `stress` from March 12 through
March 16, while the reported regime remained `uptrend` through March 15 and
changed to `stress` on March 16:

| Date | Chain | Drawdown | Price vs SMA200 | 90-day return | Raw | Reported | Days | Active flags |
|---|---|---:|---:|---:|---|---|---:|---|
| 2020-03-12 | BTC | -0.633414287678 | -0.443179198066 | -0.338704522159 | stress | uptrend | 41 | deep_drawdown, high_volatility |
| 2020-03-15 | BTC | -0.590546670943 | -0.372913329717 | -0.222066479776 | stress | uptrend | 44 | deep_drawdown, high_volatility |
| 2020-03-16 | BTC | -0.615927385480 | -0.410242898874 | -0.240774960672 | stress | stress | 1 | deep_drawdown, high_volatility |
| 2020-03-12 | ETH | -0.682312383983 | -0.398843685698 | -0.255386740331 | stress | uptrend | 33 | deep_drawdown, high_volatility |
| 2020-03-15 | ETH | -0.635286838151 | -0.306599488941 | -0.067430121299 | stress | uptrend | 36 | deep_drawdown, high_volatility |
| 2020-03-16 | ETH | -0.672883703114 | -0.377067650610 | -0.089104036757 | stress | stress | 1 | deep_drawdown, high_volatility |

### BNB: 2022-11-10

On November 10, drawdown was `-0.532882606023`, so the raw rule selected
`stress` before evaluating trend; price versus SMA200 was `0.060073751842`,
while the 90-day return was `-0.072888075633`. The verified
`deep_drawdown` flag was medium severity with value `-0.532882606023` and
threshold `-0.400000000000`.

The reported regime was still `uptrend`: raw `uptrend` held for five
consecutive days from November 3 through November 7, confirming that reported
regime on November 7. Raw `range` appeared on November 8, then raw `stress`
from November 9 through November 12. Neither subsequent raw label lasted five
consecutive days in that interval, so hysteresis retained the reported
`uptrend`. This is the rules working as designed, not a bug.

| Date | Drawdown | Price vs SMA200 | 90-day return | Raw | Reported | Days |
|---|---:|---:|---:|---|---|---:|
| 2022-11-03 | -0.495791889824 | 0.137265730163 | 0.043051598607 | uptrend | stress | 175 |
| 2022-11-07 | -0.484315225708 | 0.168874637328 | 0.038840937115 | uptrend | uptrend | 1 |
| 2022-11-08 | -0.496926859250 | 0.137139195354 | -0.004257907543 | range | uptrend | 2 |
| 2022-11-09 | -0.589274738783 | -0.069440358716 | -0.173980222497 | stress | uptrend | 3 |
| 2022-11-10 | -0.532882606023 | 0.060073751842 | -0.072888075633 | stress | uptrend | 4 |
| 2022-11-11 | -0.553779963122 | 0.014664416516 | -0.104532839963 | stress | uptrend | 5 |
| 2022-11-12 | -0.565457897972 | -0.010107197550 | -0.109571788413 | stress | uptrend | 6 |

### Latest-day coverage and provider dates

On the UTC date 2026-11-20, BTC's latest score date was November 19. Coverage
was `0.6000`, below its `0.7000` registry maximum, after being `0.7000` on each
of the previous five score dates. The November 19 component rows for
`hashrate_chg90` and `fees_usd_chg90` were absent; their trailing windows
contained 1,094 feature rows, and both source series (`hashrate` and
`fees_usd`, Blockchain.info) had `series_coverage.last_date = 2026-11-18`.
This verifies that those two series were one complete UTC day behind the other
inputs in this snapshot and coincided with the BTC coverage decrease. It does
not establish a general publication schedule.

All other registered score-input series ended on November 19, the latest
complete UTC day available on November 20. That one-calendar-day offset is
expected by design, not a provider lag. BTC Blockchain.info hashrate and fees
ended on November 18, one complete UTC day behind that baseline (two calendar
days before November 20). A typical or persistent provider-lag pattern beyond
this snapshot is **UNVERIFIED**.

### Interpretation guidance

The score is relative to each chain's own trailing three-year history, not an
absolute or cross-chain measure. Always show confidence beside the score. It
describes historical conditions; it is not a prediction, financial advice, or
a buy/sell call.

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
