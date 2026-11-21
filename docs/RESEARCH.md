# Historical research reports

These are read-only, historical checks of the currently shipped scenario,
Health Score, and regime methods. The protocol was committed first at
[`b897977`](https://github.com/parhammalekpour/chaincompass/commit/b8979770191ec43c029b96a403ada25c8c39ae6a).
All interpretation below follows the fixed [pre-registered protocol](RESEARCH_PROTOCOL.md);
the reports do not change product behavior or establish predictive accuracy.
The `--study all` CLI run took 305.065 seconds.

## Study S — historical scenario calibration

For each chain and 30-, 90-, and 365-day horizon, the shipped `scenarios-v1`
quantiles are compared with exact-date realized returns from the same
Binance `price_close_usd` series. Calibration is reported for overlapping
origins and for non-overlapping origins; Wilson 95% intervals are shown only
for the latter. The comparison-only B1 method uses a rolling 1,095-day window.
The [complete Study S tables](research/S.md) include all chains, horizons,
pooled and per-era (`E1`, `E2`) cells, sample sizes, the low/normal sample
groups, method comparisons, and paired pinball losses.

Notable results:

- The pooled 30-day scenarios-v1 hit-rate interval excludes the registered
  0.80 reference for BTC (0.896; `n=106` independent origins, 95% CI
  0.824–0.941), ETH (0.887; `n=106`, 0.812–0.934), and BNB (0.904; `n=104`,
  0.832–0.947). Each is **miscalibrated** under the fixed rule. See the report
  for below-p10 and above-p90 intervals and all-era labels.
- SOL's pooled 90-day hit rate is 1.000 (`n=19`, 95% CI 0.830–1.000), and is
  **miscalibrated** because this interval excludes 0.80.
- BTC, ETH, and BNB each have only `n=3` non-overlapping 365-day v1 origins.
  Their 1.000 hit rates have wide intervals (0.439–1.000) and receive the
  pre-registered **well calibrated** label because the intervals contain the
  reference rates. That label is not strong evidence with three origins.
- SOL has no eligible 365-day v1 origins and is **inconclusive** at that
  horizon.
- B1 has no eligible 365-day origins: the pre-registered rolling-window rule
  requires three independent windows, but the 1,095-day window does not
  contain enough complete 365-day return windows to reach that floor. This is
  reported as unavailable, not filled or reinterpreted.

The many all-origin observations are heavily overlapping and descriptive
only. B1 remains comparison-only; neither these labels nor pinball-loss
differences are a decision to change scenarios-v1.

## Study H — Health Score and forward-return association

Scores are sampled every 30 or 90 calendar days from each chain's first score
date, with exact forward returns and expanding, past-only score terciles.
Approximate Fisher-z intervals use the non-overlapping sample size. The
[complete Study H table](research/H.md) lists `n` and independent `n`, each
correlation and interval, and tercile counts and forward-return summaries.

For all eight chain/horizon cells, the approximate 95% interval contains zero;
each is therefore **association not distinguishable from zero** under the
registered rule. The observed tercile means and medians vary across chains
and horizons and are descriptive only. Health Score inputs include
price-derived market-condition components, so an association could reflect
mechanical momentum or mean-reversion rather than on-chain information. No
association is described as predictive.

## Study R — regime v1 versus comparison v2

V1 reproduces the stored regime rows for every chain (zero mismatches).
Compared with v1, immediate stress entry and five-day stress exit in v2
increased reported switches in every chain:

| Chain | V1 switches / episodes | V2 switches / episodes | V1 episodes under 10 days | V2 episodes under 10 days |
|---|---:|---:|---:|---:|
| BTC | 55 / 56 | 60 / 61 | 12 | 15 |
| ETH | 51 / 52 | 58 / 59 | 6 | 12 |
| SOL | 32 / 33 | 43 / 44 | 5 | 16 |
| BNB | 57 / 58 | 60 / 61 | 10 | 13 |

These counts show the registered comparison's trade-off: earlier stress entry
is accompanied by more switching and more short episodes in this stored
history. V2 is **not adopted**. The [complete Study R tables](research/R.md)
include duration summaries and detection/exit lags for each raw-stress episode;
the JSON reports also identify right-censored observations.

## What this does and does not show

This report describes calibration, historical association, and regime-state
behavior on the stored data under one fixed protocol. The small independent
samples, particularly at 365 days, make intervals wide. Pooled historical
behavior can conceal differences between eras, and all-origin scenario counts
must not be mistaken for independent evidence. Missing source dates remain
gaps; they are not interpolated.

The analysis does not establish predictive power, forecast accuracy, future
regime behavior, or investment outcomes. It does not provide financial advice
or buy/sell recommendations. The score association study is not evidence that
the Health Score contains predictive on-chain information.

## Limitations

- Maximum score-input coverage is BTC 0.70, ETH 0.90, SOL 0.60, and BNB 0.60;
  available inputs differ by chain.
- SOL price history begins in 2020-08. BNB prices begin in 2017-11, but its
  score history begins in 2022.
- A 365-day scenario horizon has only a handful of independent origins.
  B1 has no eligible 365-day origins under its fixed availability floor.
- Crypto history contains only a few market regimes. Binance USDT close is a
  USD proxy; source gaps, partial coverage, and the approximate Fisher-z
  interval constrain interpretation.
- Past-only expanding terciles require at least 30 prior score dates, reducing
  the already-small tercile samples.

## What would change my mind

A stronger calibration conclusion would require a separately pre-registered
evaluation with substantially more independent origins, narrow intervals, and
consistent results across multiple held-out eras and chains. Any proposed
scenario or regime revision would need its own protocol and independent
evaluation; no method was tuned or adopted from these results.

## Reproducible outputs

The generated [Study S JSON](research/S.json), [Study H JSON](research/H.json),
and [Study R JSON](research/R.json) record the protocol commit hash, methods,
sample counts, metrics, intervals, and exclusions. Their paired Markdown
reports are linked above. Files contain no run timestamp or raw database dump.
