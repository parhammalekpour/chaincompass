# Historical Volatility-Risk Study Protocol

**Pre-registered before any model code or result exists.**

Protocol date: 2026-11-26 (UTC)  
Protocol revision: 1  
The commit that introduces this file is the protocol commit. Later results must
cite that commit hash; it is intentionally not embedded here.

## 0. Header and revision note

This protocol was revised after an external LLM review. That review is
UNVERIFIED: the reviewer had no repository access, and an LLM review is not an
expert review. Adopted changes: a HAR-style baseline; comparators fixed in
advance; synchronized block bootstrap with a 60-day sensitivity run;
calibration slope and intercept; ECE moved to the live-card gate; explicit
label maturity; and Part 2 pre-registered.

## 1. Purpose

A small educational scikit-learn study of historical volatility risk. This is
not a price or direction forecast and is not advice. A NEGATIVE result is a
valid outcome and will be published.

## 2. Label

Let `r(d) = ln(close(d) / close(d-1))`.

- `RV30(s)` is the sample standard deviation (`ddof=1`) of returns on days
  `s-29..s`, multiplied by `sqrt(365)`.
- `RV30_fwd(t)` is the same statistic over days `t+1..t+30`.
- `Q80(t)` is the Hyndman-Fan type 7 80th percentile of
  `{RV30(s) : s <= t}`. It uses only windows ending on or before `t`; each
  `RV30(s)` is observable at `s`. The window expands and requires at least 365
  valid values.
- `y(t) = 1` if `RV30_fwd(t) > Q80(t)`, otherwise `y(t) = 0`.
- Any window containing a missing close is invalid. No filling or
  interpolation is used. Only complete UTC days are used.
- `y(t)` is known only at `t+30`; section 6 handles maturity with purging.

## 3. Part 1 features

Past-only, scale-free features: `RV30`, `RV90`, `RV30/RV90`, `ret_30d`,
`ret_90d`, `drawdown_365d`, `price_vs_sma200`, and `volume_ratio_30_365`, plus
the point-in-time expanding percentile rank of each feature.

The ML module recomputes these from daily closes and volume, independently of
the stored features. Appendix A records stored-feature differences.

- `RV90` uses the `RV30` definition with a 90-day return window.
- `ret_k = ln(close(t)/close(t-k))`, for `k = 30, 90`.
- `drawdown_365d = close(t) / max(close over t-364..t) - 1`.
- `price_vs_sma200 = close(t) / mean(close over t-199..t) - 1`.
- `volume_ratio_30_365 = mean(volume over t-29..t) / mean(volume over
  t-364..t)`.
- The expanding percentile rank of feature `f` at `t` is the fraction of
  `{f(s): s <= t}` that is `<= f(t)`. It requires at least 365 values;
  otherwise the row is ineligible.

No Health Score, regime, or on-chain feature is used in Part 1: these are
derived from price or other stored measurements and could create circularity.
Standardization uses training-fold statistics only. A row is ineligible if
any required feature value cannot be computed.

## 4. Baselines

Comparators are fixed in advance.

- **B0 — base rate:** training-fold frequency of `y`.
- **B1 — persistence:** training-fold frequency of `y` conditional on
  `[RV30(t) > Q80(t)]`.
- **B2 — stored `vol_state` lookup:** training-fold frequency of `y`
  conditional on the stored `vol_state` category; retained only if Appendix A
  shows `vol_state` is CAUSAL, otherwise it is dropped and the reason is
  recorded.
- **B3 — HAR-style:** OLS of `ln(RV30_fwd)` on `[1, ln(RV7), ln(RV30),
  ln(RV90)]`, fitted on the training fold. `RV7` uses the same statistic over
  a 7-day window. Let `sigma` be residual standard deviation on the training
  fold. Then
  `P(y=1) = 1 - Phi((ln Q80(t) - prediction) / sigma)`, with `Phi` computed
  using `math.erf`. This adapts HAR-RV to daily data; it is not the original
  specification.

## 5. Models

`random_state=12345` everywhere. No hyperparameter tuning and no calibration
step.

- **M1:** `LogisticRegression` (L2, `C=1.0`, `max_iter=1000`).
- **M2:** `HistGradientBoostingClassifier` (`max_depth=3`,
  `learning_rate=0.05`, `max_iter=200`, `early_stopping=False`).
- **M3:** `MLPClassifier` (`hidden_layer_sizes=(16,)`, `alpha=0.01`,
  `max_iter=500`, `early_stopping=False`). Exploratory, lowest priority.

## 6. Protocol

Pool the four chains. Use calendar-date folds with an expanding training
window, an initial training period of at least 730 days, and 90-day test
blocks. Purge training rows whose `t > test_start - 31 days`, because labels
look 30 days ahead. Within each fold, all models and comparators use identical
eligible rows.

## 7. Metrics

Brier score is primary. Also report log loss, AUC, a reliability table with
10 equal-count bins and ECE, and calibration slope and intercept from
unpenalized logistic regression of `y` on `logit(p)`, with `p` clipped to
`[1e-6, 1-1e-6]`.

Report pooled metrics, each chain, the macro-average across chains, both
chronological halves, and calendar years (supplementary only).

## 8. Uncertainty

Use moving-block bootstrap over calendar dates, synchronized across chains
(the same date blocks apply to every chain). Use block length 30 days as
primary and 60 days for sensitivity; 2,000 resamples and seed 12345. Compute
paired differences against each comparator. Use Bonferroni-adjusted intervals
at level `1 - 0.05/3`.

## 9. Success criteria

- **Tier A**, assessed against each comparator in `{B1, B3, and B2 if kept}`:
  (i) the upper bound of the pooled paired Brier-difference confidence
  interval is below zero at both block lengths; (ii) pooled relative Brier
  improvement is at least 2%; (iii) Brier score is lower in at least 3 of 4
  chains; and (iv) Brier score is lower in both chronological halves.
- **Tier B**, M1 only and required for any live card: Tier A plus calibration
  slope in `[0.8, 1.2]` and ECE at most `0.05`.
- Otherwise the result is **NEGATIVE**. M2 and M3 appear on the Lab page only
  and cannot trigger a live card.

## 10. Informativeness

If the pooled test set has fewer than 100 positive labels, or any chain's test
set has fewer than 20, label the result **NOT INFORMATIVE**.

## 11. Leakage controls

All controls must pass before any result is produced:

1. A unit test shows features, `RV30`, and `Q80` at `t` are unchanged when data
   after `t` is altered.
2. A unit test confirms every `RV30(s)` used in `Q80(t)` has `s <= t`.
3. A label-permutation run has AUC approximately 0.5.
4. A leaky canary using `RV30_fwd` as a feature has near-perfect AUC.

## 12. Reproducibility

Provide one CLI command against the local database and fixed seeds. Output
records a dataset hash and the protocol commit hash. Do not commit raw prices.
Publish all results on the Lab page, whatever the outcome. Any change is a
dated amendment written before another run.

## 13. Storage and exposure

This is future work and applies only if the live-card gate is met. Use `float`
only inside the training module; store values as Decimal strings. Store M1 as
JSON (coefficients, intercept, feature names, standardization statistics,
data hash, and protocol commit hash); do not use pickle.

Required wording: “experimental historical volatility-risk estimate, not a
forecast”. An optional read-only agent tool `get_risk_model_estimate` may be
added only if the live card is approved, and must follow the same
number-grounding rules.

## 14. Dependencies

Add scikit-learn and numpy to an optional research dependency group, not the
default runtime install.

## 15. Limitations

Overlapping labels reduce effective sample size to about `n/30`; chains are
correlated; there is one historical path; hyperparameters are fixed; the HAR
baseline is an adaptation; thresholds are a priori; and results use one data
snapshot at course scale. An LLM review is not an expert review.

Expectation (a guess, not a result): volatility clusters, so persistence may
be strong and the models may add little.

## 16. Part 2 — planned after Part 1

Question: “Do fundamental metrics add information about volatility risk
beyond price features?”

- Use the same label, walk-forward folds, purge, and fixed M1 (M2 exploratory).
- Compare feature set **P**, the Part 1 price-only features, with **PF**, P
  plus the 90-day log change of each available fundamental series:
  `active_addresses`, `tx_count`, `tvl_usd`, `stablecoin_supply_usd`,
  `dex_volume_usd`, and `hashrate`.
- Per-chain availability: BTC `active_addresses`, `tx_count`, `hashrate`;
  ETH `active_addresses`, `tx_count`, `tvl_usd`, `stablecoin_supply_usd`,
  `dex_volume_usd`; SOL and BNB `tvl_usd`, `stablecoin_supply_usd`,
  `dex_volume_usd`, as stored and subject to Appendix A verification.
- A log change is undefined if either value is `<= 0`; exclude that row. Run
  per chain on identical rows for P and PF, with no imputation and no
  forward-fill.
- A fundamental value is usable at `t` only if its complete UTC day is
  `<= t`. Vintage/revision risk and unverified DEX-volume units are
  limitations.
- Per-chain success requires the Bonferroni-adjusted `(1 - 0.05/4)`
  block-bootstrap confidence-interval upper bound for paired Brier difference
  `(PF - P)` to be below zero at both block lengths, and relative improvement
  to be at least 2%.
- Claim “fundamentals add information” only if at least 2 of 4 chains succeed;
  otherwise report **NEGATIVE** or **INCONCLUSIVE**. Sections 10 and 11 apply.
  Wording is limited to statistical information about volatility risk; no
  trading claim.

## Appendix A: Verified facts at protocol time

Checked 2026-11-26 UTC from the codebase and local PostgreSQL using
SELECT-only queries. Observation dates below are database `obs_date` values.
No data was changed.

### A(a). Stored daily feature computation

The implementation is in `backend/app/analytics/features.py`, principally
`compute_series_features`, `_append_price_features`, `_append_volume_features`,
`_input_window`, `_median_window`, and `_required_coverage`.
For every feature date, the routine processes points dated up to that date;
the per-date 30-consecutive-nonzero effective-start gate is also advanced
point-in-time. It does not use later observations to calculate that date.

| Stored feature | Lookback and day-t inclusion | Stored calculation and missing-data rule | Causal |
|---|---|---|---|
| `realized_vol_30d` | 30 one-day log returns dated `t-29..t`; includes return day `t` and uses close pairs spanning `t-30..t` | Sample standard deviation, `ddof=1`, annualized by `sqrt(365)`; needs at least 27 of 30 returns (90%); no filling | Yes |
| `realized_vol_90d` | 90 one-day log returns dated `t-89..t`; includes `t`, spanning closes `t-90..t` | Sample standard deviation, `ddof=1`, annualized by `sqrt(365)`; needs at least 81 of 90 returns (90%); no filling | Yes |
| `ret_30d` | Endpoint closes `t-30` and `t`; both endpoints are used | Simple return `close(t)/close(t-30)-1`; intermediate closes are not required | Yes |
| `ret_90d` | Endpoint closes `t-90` and `t`; both endpoints are used | Simple return `close(t)/close(t-90)-1`; intermediate closes are not required | Yes |
| `drawdown_365d` | 365 closes `t-364..t`, inclusive of `t` | `close(t)/max(available closes)-1`; at least 329 of 365 closes (90%); no filling | Yes |
| `price_vs_sma200` | 200 closes `t-199..t`, inclusive of `t` | `close(t)/arithmetic mean(available closes)-1`; at least 180 of 200 closes (90%); no filling | Yes |
| `volume_ratio_30_365` | Both quote-volume windows include `t`: 30 days `t-29..t` and 365 days `t-364..t` | Median of available 30-day values divided by median of available 365-day values; the 30-day window needs at least 24 observations, and the 365-day window at least 329; denominator must be positive | Yes |

For comparison, this protocol recomputes features using its stated windows and
requires complete windows. The stored `ret_30d` and `ret_90d` are simple
returns, while Part 1 uses log returns. The stored volume ratio uses medians;
Part 1 specifies means. Stored realized-volatility features allow 90%
coverage, while the registered label and ML features invalidate a window
containing any missing close. `RV7` is not a stored feature and is recomputed
for B3. Stored calculations use Decimal arithmetic and quantize feature
values to 12 decimal places.

Daily volume is stored in `observations` with metric key `volume_usd`, source
`binance`, and one date-keyed row per chain/day. The Binance kline provider
reads quote volume (`row[7]`) and converts the candle open timestamp to a UTC
date; its quote currency is USDT, so `volume_usd` is a USD proxy, not a
separately verified USD-denominated volume. The source table also records
`fetched_at`; it is not a historical data-vintage record.

### A(b). Stored `vol_state` causality

**CAUSAL.** `backend/app/analytics/scoring.py`,
`point_in_time_percentiles`, orders realized-volatility records by date and
adds only records with `as_of_date <= t`; it then removes records older than
the rolling 1,095-calendar-day window ending at `t`. At least 365 observations
are required. The current value is ranked against this point-in-time window
using a midrank for ties. `compute_analytics` supplies this rank for
`realized_vol_90d`, and `_regime_values` maps ranks `>= 80` to high,
`<= 20` to low, and other ranks to normal. These are rolling point-in-time
percentile ranks, not thresholds fitted on the full sample. `vol_state` is
therefore eligible for B2 under the pre-registered rule.

### A(c). Daily close coverage

The query counted stored `price_close_usd` / `binance` observations and checked
every calendar date between each chain's first and last close. The ingestion
provider converts Binance daily candle open times to UTC dates. These are
complete, gap-free UTC date sequences in this database snapshot.

| Chain | First date | Last date | Rows | Calendar gaps |
|---|---|---|---:|---:|
| BTC | 2017-08-17 | 2026-11-19 | 3,382 | 0 |
| ETH | 2017-08-17 | 2026-11-19 | 3,382 | 0 |
| SOL | 2020-08-11 | 2026-11-19 | 2,292 | 0 |
| BNB | 2017-11-06 | 2026-11-19 | 3,301 | 0 |

### A(d). Fundamental and other stored observation series

Each row gives the exact database metric key, source, first and last
`obs_date`, row count, and calendar-gap count within that series' own date
range. For gap counts of 10 or fewer, the missing dates are listed. Metric
keys, units, and daily frequency were also read from `metric_definitions`.
`market_cap_usd` appears from two sources where shown. Database-declared units
are daily: `active_addresses` (addresses), `tx_count` (transactions),
`hashrate` (H/s), and the `_usd` keys (USD). These declarations do not
independently verify provider-specific semantics; DEX-volume units are
UNVERIFIED. The `validators` key is defined but has no observation rows for
these four chains. No other observation series were found for these chains
beyond the rows listed here, their `price_close_usd`, and their `volume_usd`.

| Chain | Metric key | Source | First date | Last date | Rows | Gaps and dates when <=10 |
|---|---|---|---|---|---:|---|
| BTC | `active_addresses` | `coin_metrics` | 2017-01-01 | 2026-11-19 | 3,610 | 0 |
| BTC | `dex_volume_usd` | `defillama` | 2017-01-01 | 2026-11-19 | 3,610 | 0; unit semantics UNVERIFIED |
| BTC | `fees_usd` | `blockchain_info` | 2017-08-17 | 2026-11-18 | 3,378 | 3: 2025-11-13, 2025-11-14, 2025-11-15 |
| BTC | `hashrate` | `blockchain_info` | 2017-01-01 | 2026-11-18 | 3,606 | 3: 2025-11-13, 2025-11-14, 2025-11-15 |
| BTC | `market_cap_usd` | `coin_metrics` | 2017-01-01 | 2026-11-19 | 3,610 | 0 |
| BTC | `market_cap_usd` | `coingecko` | 2026-11-18 | 2026-11-19 | 2 | 0 |
| BTC | `protocol_fees_usd` | `defillama` | 2021-04-12 | 2026-11-19 | 1,954 | 94 |
| BTC | `tx_count` | `coin_metrics` | 2017-01-01 | 2026-11-19 | 3,610 | 0 |
| ETH | `active_addresses` | `coin_metrics` | 2017-01-01 | 2026-11-19 | 3,610 | 0 |
| ETH | `dex_volume_usd` | `defillama` | 2018-11-02 | 2026-11-19 | 2,940 | 0; unit semantics UNVERIFIED |
| ETH | `market_cap_usd` | `coin_metrics` | 2017-01-01 | 2026-11-19 | 3,610 | 0 |
| ETH | `market_cap_usd` | `coingecko` | 2026-11-18 | 2026-11-19 | 2 | 0 |
| ETH | `protocol_fees_usd` | `defillama` | 2018-03-26 | 2026-11-19 | 3,155 | 6: 2018-04-27, 2018-05-18, 2018-06-11, 2018-07-04, 2018-07-06, 2018-07-07 |
| ETH | `stablecoin_supply_usd` | `defillama` | 2017-11-29 | 2026-11-19 | 3,278 | 0 |
| ETH | `tvl_usd` | `defillama` | 2017-09-27 | 2026-11-19 | 3,341 | 0 |
| ETH | `tx_count` | `coin_metrics` | 2017-01-01 | 2026-11-19 | 3,610 | 0 |
| SOL | `dex_volume_usd` | `defillama` | 2021-10-02 | 2026-11-19 | 1,872 | 3: 2021-10-03, 2021-10-04, 2021-12-09; unit semantics UNVERIFIED |
| SOL | `market_cap_usd` | `coingecko` | 2026-11-18 | 2026-11-19 | 2 | 0 |
| SOL | `protocol_fees_usd` | `defillama` | 2022-02-14 | 2026-11-19 | 1,740 | 0 |
| SOL | `stablecoin_supply_usd` | `defillama` | 2021-09-10 | 2026-11-19 | 1,654 | 243 |
| SOL | `tvl_usd` | `defillama` | 2021-03-17 | 2026-11-19 | 2,074 | 0 |
| BNB | `dex_volume_usd` | `defillama` | 2020-09-19 | 2026-11-19 | 2,253 | 0; unit semantics UNVERIFIED |
| BNB | `market_cap_usd` | `coingecko` | 2026-11-18 | 2026-11-19 | 2 | 0 |
| BNB | `protocol_fees_usd` | `defillama` | 2021-02-17 | 2026-11-19 | 2,102 | 0 |
| BNB | `stablecoin_supply_usd` | `defillama` | 2020-08-29 | 2026-11-19 | 2,223 | 51 |
| BNB | `tvl_usd` | `defillama` | 2020-10-30 | 2026-11-19 | 2,212 | 0 |

The Part 2 feature availability stated in section 16 is confirmed by stored
rows: BTC has active addresses, transaction count, and hashrate; ETH has
active addresses, transaction count, TVL, stablecoin supply, and DEX volume;
SOL and BNB have TVL, stablecoin supply, and DEX volume. Additional stored
series are listed above; market capitalization, protocol fees, and BTC DEX
volume are not in the Part 2 feature set. `dex_volume_usd` unit semantics
remain UNVERIFIED.

### Approximate eligible row counts

These are approximate Part 1 row counts after the full feature and label
eligibility rules, not a training/test count. Daily close and volume rows are
gap-free. The earliest full-window feature (`drawdown_365d` and the
365-day volume ratio) begins at close index 364; its expanding rank first has
365 values at index 728. Future label maturity removes the final 30 origins.
Thus the rough count is daily close rows minus 758:

| Chain | Approximate eligible rows |
|---|---:|
| BTC | 2,624 |
| ETH | 2,624 |
| SOL | 1,534 |
| BNB | 2,543 |

This count assumes all price/volume feature values are computable; exact
eligibility and the number of positive labels remain UNVERIFIED until the
registered dataset construction is implemented. Each chain has more than
1,500 approximate eligible rows, so the inventory does not make the fixed
walk-forward design impossible. Final informativeness under section 10
remains an empirical, UNVERIFIED outcome.

## Amendment A1 (dated 2026-11-26, written before any result)

1. **Data cutoff:** `DATA_CUTOFF = 2026-11-19`, the last complete UTC close in
   the local database at protocol time. Ignore observations dated after the
   cutoff. An origin `t` is eligible only when `t+30 <= DATA_CUTOFF`.
2. **Eligibility:** All models and comparators use identical rows. At origin
   `t`, every feature, `RV7`, `RV30`, `Q80`, and `RV30_fwd` must be
   computable with no missing close inside any required window. Each expanding
   feature percentile rank needs at least 365 values; `Q80` needs at least 365
   `RV30` values. Required logs must be defined (`RV7`, `RV30`, and `RV90`
   positive; volume mean positive). Otherwise the row is ineligible. The 16
   model features are `RV30`, `RV90`, `RV30/RV90`, `ret_30d`, `ret_90d`,
   `drawdown_365d`, `price_vs_sma200`, and `volume_ratio_30_365`, plus the
   expanding percentile rank of each of those eight. `RV7` and log values are
   inputs to B3 only.
3. **Fold schedule:** `first_eligible_date` is the earliest eligible origin
   across all chains. `test_start_k = first_eligible_date + 730 days + 90*k
   days`, for `k = 0, 1, 2, ...`. Test block `k` contains pooled origins
   `test_start_k <= t < test_start_k + 90 days`; include a final partial
   block shorter than 90 days. Training rows for fold `k` are all eligible
   origins from all chains with `t <= test_start_k - 31 days`. A chain with
   no eligible rows in a block is absent from that block.
4. **Leakage-check tolerances:** These are pre-set sanity thresholds, not
   performance claims. For (c), run 20 permutations of `y` using seeds
   `12345..12364`, each shuffling `y` over all eligible rows; use fixed M1,
   the same folds, and pooled test AUC per permutation. PASS when the mean of
   the 20 AUCs is in `[0.45, 0.55]`. For (d), add the single canary feature
   `ln(RV30_fwd/Q80)`; PASS when pooled test AUC is at least `0.99`. Failure
   of (c) or (d) means STOP and investigate a genuine bug; do not tune.
5. **Purge test (e):** For every fold, every training row must satisfy
   `t + 30 days < test_start`.
6. **Dataset hash:** SHA-256 over rows sorted by `(chain, date)`. Serialize
   each row as `"chain|date|y|"` plus all model features, `RV7`, `RV30`,
   `Q80`, and `RV30_fwd` in a fixed order, each float formatted with
   `format(x, ".12e")`. Prepend the cutoff date. Do not hash model output.
7. Until all leakage checks (a)-(e) are green, no model is fit on true labels.

## Amendment A2 (dated 2026-11-26, written before any result)

This amendment supersedes the original section 10 informativeness rule, Tier A
criterion (iii) in section 9, and the Part 2 chain-count rule in section 16.
It is based only on label counts; no model performance has been seen.

1. **Motivation and observed counts:** The 11G-2 `build-dataset` output gives
   the following eligible row and positive-label counts:

   | Chain | Eligible rows | Positive labels |
   |---|---:|---:|
   | BTC | 2,624 | 164 |
   | ETH | 2,624 | 173 |
   | SOL | 1,534 | 42 |
   | BNB | 2,543 | 164 |
   | Pooled | 9,325 | 543 |

   Summed over the union of all test blocks, the counts are:

   | Chain | Test rows | Test positives |
   |---|---:|---:|
   | BTC | 1,894 | 38 |
   | ETH | 1,894 | 58 |
   | SOL | 1,534 | 42 |
   | BNB | 1,894 | 0 |
   | Pooled | 7,216 | 138 |

   All 164 BNB positive labels are dated 2020-02-11 through 2021-05-30,
   before the first test block starts on 2021-08-14; they fall in the
   training-only initial period. Thus BNB has no positives in the test union.
2. **Amended informativeness rule:** Evaluate informativeness on the union of
   all test blocks, not separately per fold; per-fold counts are descriptive.
   (i) If the pooled test union has fewer than 100 positive labels, the whole
   result is **NOT INFORMATIVE**. (ii) A chain with fewer than 20 positive
   labels over that union is labelled **chain not informative**. Its results
   are still reported descriptively, including Brier score, and its rows
   remain in pooled evaluation; it is excluded from Tier A criterion (iii),
   the per-chain macro-average, and the Part 2 chain count. (iii) If fewer
   than 2 chains are informative, the whole result is **NOT INFORMATIVE**.
3. **Tier A criterion (iii):** Replace “Brier score is lower in at least 3 of
   4 chains” with “Brier score is lower in at least
   `ceil(0.75 * n_inf)` of the `n_inf` informative chains.” With 4 informative
   chains this requires 3; with 3 it requires all 3.
4. **Part 2:** A chain counts toward “at least 2 of 4 chains succeed” only if
   it is informative on Part 2's own identical P/PF test rows. Apply the same
   100 pooled-positive and 20 per-chain-positive rules to those rows; fewer
   than 2 informative chains makes the whole Part 2 result **NOT INFORMATIVE**.
5. Labels, features, folds, models, hyperparameters, metrics, bootstrap
   settings, and all other thresholds are unchanged.
6. **Limitation (hypothesis, unverified):** The measured positive rate is
   543/9,325 (5.82%) overall and 138/7,216 (1.91%) over the test union, far
   below the nominal 20%. The expanding Q80 is anchored by the very high
   volatility of 2017-2021; whether that explains the lower rates is a
   hypothesis and remains unverified.
