# Historical research reports

## Machine-learning study

The [pre-registered historical volatility-risk protocol](ML_PROTOCOL.md)
records the proposed study and its fixed evaluation rules.

Study 1 implemented and run on 2026-11-26; Part 2 planned; no live model on the site. Study 1 verdict: **NEGATIVE** — see [ML_RESULTS.md](ML_RESULTS.md).

Future work: Evidence-tuple grounding (chain, metric, value, unit, date) for the agent.

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

## Post-hoc notes (added after results were seen)

These notes describe the fixed outputs; they do not alter any label or
pre-registered rule. Labels in the tables remain exactly as registered. The
rule did not specify a minimum sample size, so the labels for every cell with
fewer than 20 non-overlapping origins are not informative: BTC, ETH, SOL, and
BNB at 365 days (`n=3`, `n=3`, `n=0`, and `n=3`, respectively), and SOL at
90 days (`n=19`).

For the pooled scenarios-v1 hit rates below, a rate above 0.80 means the
p10-p90 band was wider than nominal; a rate below 0.80 means it was narrower.
The rates and directions are descriptive and retain the original sample sizes.

| Chain | Horizon | Independent n | P10-p90 hit rate | Direction |
|---|---:|---:|---:|---|
| BTC | 30 | 106 | 0.896 | Wider |
| BTC | 90 | 31 | 0.903 | Wider |
| BTC | 365 | 3 | 1.000 | Wider; very small sample |
| ETH | 30 | 106 | 0.887 | Wider |
| ETH | 90 | 31 | 0.871 | Wider |
| ETH | 365 | 3 | 1.000 | Wider; very small sample |
| SOL | 30 | 70 | 0.871 | Wider |
| SOL | 90 | 19 | 1.000 | Wider; very small sample |
| SOL | 365 | 0 | — | Not assessable |
| BNB | 30 | 104 | 0.904 | Wider |
| BNB | 90 | 30 | 0.900 | Wider |
| BNB | 365 | 3 | 1.000 | Wider; very small sample |

No available pooled scenarios-v1 cell has a hit rate below 0.80. Despite the
hit rates being closer to 0.80 for B1 in some cells, that alone does not mean
B1 is better. The paired non-overlapping mean pinball losses below come
directly from the existing Study S JSON. Lower values are not an adoption
criterion; `n` is the shared paired sample size.

| Chain | Horizon | Paired n | V1 p10 / p50 / p90 | B1 p10 / p50 / p90 |
|---|---:|---:|---|---|
| BTC | 30 | 106 | 0.031385 / 0.077385 / 0.041425 | 0.031763 / 0.078601 / 0.040407 |
| BTC | 90 | 31 | 0.058665 / 0.184231 / 0.096817 | 0.067176 / 0.191856 / 0.098438 |
| BTC | 365 | 0 | — / — / — | — / — / — |
| ETH | 30 | 106 | 0.041943 / 0.108706 / 0.053512 | 0.042645 / 0.110327 / 0.053140 |
| ETH | 90 | 31 | 0.075199 / 0.244992 / 0.132353 | 0.082460 / 0.253968 / 0.146155 |
| ETH | 365 | 0 | — / — / — | — / — / — |
| SOL | 30 | 70 | 0.055779 / 0.165873 / 0.122734 | 0.056611 / 0.165631 / 0.110126 |
| SOL | 90 | 19 | 0.063453 / 0.246999 / 0.433841 | 0.066535 / 0.251301 / 0.324990 |
| SOL | 365 | 0 | — / — / — | — / — / — |
| BNB | 30 | 104 | 0.040116 / 0.099847 / 0.084527 | 0.040289 / 0.100305 / 0.078545 |
| BNB | 90 | 30 | 0.081095 / 0.298258 / 0.402527 | 0.079130 / 0.301920 / 0.395389 |
| BNB | 365 | 0 | — / — / — | — / — / — |

All eight Study H point estimates are positive, all eight approximate
intervals contain zero, and eight chain/horizon tests were run. Score inputs
include price-derived components; no association is claimed.

The following Study R summaries use the stress-lag arrays in the existing
JSON. Means and medians use only episodes with an observed lag; `n` shows how
many of the raw-stress episodes contributed. A missing v2 SOL exit remains
right-censored.

| Chain | Raw episodes | V1 detection n / mean / median days | V2 detection n / mean / median days | V1 exit n / mean / median days | V2 exit n / mean / median days |
|---|---:|---|---|---|---|
| BTC | 16 | 11 / 2.18 / 4 | 16 / 0 / 0 | 11 / 9.27 / 5 | 16 / 8.44 / 5 |
| ETH | 27 | 21 / 1.90 / 0 | 27 / 0 / 0 | 21 / 16.14 / 9 | 27 / 13.96 / 8 |
| SOL | 20 | 11 / 2.18 / 4 | 20 / 0 / 0 | 11 / 49.45 / 5 | 18 / 59.33 / 5 |
| BNB | 25 | 16 / 2.75 / 4 | 25 / 0 / 0 | 16 / 28.81 / 5 | 25 / 34.80 / 11 |

End-to-end determinism against the database was not re-verified. The
determinism test covers pure JSON generation only.

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
