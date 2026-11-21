# Pre-registered walk-forward research protocol

**Status:** registered before any study result is computed. This protocol
defines a read-only, historical calibration and descriptive comparison of the
currently shipped `scenarios-v1`, Health Score `v1`, and regime `v1`. It does
not change product behavior, scenario or scoring versions, API responses, or
database contents. Results are not a forecast and will not be used to tune the
shipped methods in this study.

The research runner reads only observations, computed features, health scores,
and regimes already stored in PostgreSQL. All stored values remain
`Decimal`/`NUMERIC` through loading; conversion to floating point is permitted
only at the statistical computation boundary. Missing dates remain missing:
there is no forward-fill, interpolation, or fabricated price or feature value.

## Shared sample rules

- Chains: `btc`, `eth`, `sol`, and `bnb`.
- Price observations: exactly `price_close_usd` from `binance`, the input series
  used by the shipped scenario engine. Binance USDT quotes are a USD proxy.
- An H-day realized return at origin date `t` exists only when exact closes are
  stored at both `t` and `t + H`. It is `close(t + H) / close(t) - 1`.
  A missing endpoint excludes that outcome; dates are never filled.
- Origin calculations use data dated on or before `t`; no observation after
  `t` may enter a scenario estimate, score, or regime state at `t`.
- Decimal outputs from the application are preserved as decimal strings in
  research JSON where they represent stored values. Statistical summaries use
  finite-precision floating-point calculations only after the Decimal-to-float
  boundary described in the module documentation.
- “Pooled” means the union of eligible observations for that chain and
  horizon across the two pre-defined eras. No statistic pools different chains
  into one estimate.

## Study S — historical scenario calibration

### Methods and origins

The primary method is the shipped `scenarios-v1`, using its pure
`calculate_scenarios`, `window_returns`, and `type7_quantile` functions. Do not
reimplement its quantile or return-window calculation. For each chain and
horizon `H` in 30, 90, and 365 calendar days:

1. Consider each stored price date `t` with an exact close. Evaluate the
   shipped scenario engine with only price rows dated on or before `t` and
   `as_of_date=t`.
2. Keep the origin only when that horizon is available under the engine's
   shipped rule, `n_independent = n_windows // H >= 5`, and the exact
   `t + H` close exists. The engine's p10, p50, and p90 at `t` are compared
   with the realized return ending at `t + H`.
3. Record an origin as **low-sample** when `5 <= n_independent < 10`, and
   **normal-sample** when `n_independent >= 10`. Report both groups separately
   as well as together.
4. An unavailable scenario horizon, a missing origin close, or a missing
   `t + H` close contributes no calibration outcome. Report excluded counts
   and their reasons. Each reported `n` is the number of realized outcomes,
   not the number of stored prices or candidate dates.

The origin set is evaluated independently per chain and horizon. Outcomes are
classified with strict inequalities as below p10 (`r < p10`), below p50
(`r < p50`), above p90 (`r > p90`), and inside the p10–p90 interval
(`p10 <= r <= p90`). Equality is therefore inside the interval and is not an
outside-tail breach.

### Fixed comparison baseline B1

B1 is a comparison-only rolling calibration window of the 1,095 calendar dates
ending at and including `t` (from `t - 1094 days` through `t`). Within that
window use the same exact-date H-day return windows and the same type-7
quantile method as `scenarios-v1`. Apply the same five-independent-window
availability floor, scaled only where the 1,095-day window cannot contain five
non-overlapping windows: `minimum_independent = min(5, floor(1095 / H))`.
Thus, for H=30 and H=90 the floor is five, and for H=365 it is three. The
independent count is `number of exact H-day return windows // H`. Do not
otherwise alter B1 after viewing results.

Report the calibration metrics for each method using that method's eligible
origins and show its own `n`. For a direct baseline loss comparison, calculate
pinball loss for both methods on the shared, paired set of non-overlapping
origins where both methods are available and the realized outcome exists. State
the paired `n` beside each loss; do not imply that differing method-specific
origin counts are paired.

### Metrics and overlap

For each chain × horizon × era, and pooled across eras, report separately for
all eligible origins and for the non-overlapping sample:

- share of realized returns below p10 (reference rate 0.10);
- share below p50 (reference rate 0.50);
- share above p90 (reference rate 0.10);
- p10–p90 hit rate (reference rate 0.80).

The all-origin sample is heavily overlapping and descriptive only. The
inferential sample is selected on a fixed calendar grid: anchor at the first
eligible origin for that chain × horizon × method, then consider dates
`anchor + k * H` calendar days for integer `k >= 0`; retain a grid date only
when it is eligible. Report its `n_independent_origins` explicitly. For B1
paired pinball losses, use a grid anchored at the first common eligible origin.
Do not select origins based on return values.

Report Wilson 95% confidence intervals for each proportion only on the
non-overlapping sample. The Wilson interval uses `z=1.959963984540054`. Do not
present an all-origin confidence interval. The number of independent origins
is small, especially for 365-day horizons, and intervals are expected to be
wide; treat this as a limitation, not a reason to change the protocol.

For each quantile `q` in p10, p50, and p90, report mean pinball loss on the
paired non-overlapping sample, with loss
`max(q * (r - forecast), (q - 1) * (r - forecast))`. Report `n` beside every
loss. Lower loss is a descriptive comparison only and does not select or adopt
a method.

### Eras and pre-registered reading rule

Assign eras by **origin date**, before looking at outcomes:

- E1: `t <= 2021-12-31`.
- E2: `t >= 2022-01-01`.
- Pooled: E1 and E2 combined.

Apply the following labels to the primary shipped `scenarios-v1` cells only.
Use non-overlapping Wilson intervals:

- **well calibrated** only when the p10–p90 hit-rate interval contains 0.80
  and both the below-p10 and above-p90 intervals contain 0.10;
- **miscalibrated** when the p10–p90 hit-rate interval excludes 0.80;
- **inconclusive** in every other case.

If an interval cannot be computed, label the cell **inconclusive**. Do not use
other labels or reinterpret the rule after seeing results. B1 is comparison
only and receives no adoption label. This is a descriptive calibration check,
not a decision to change v1; any v2 requires a separate prompt and review.

## Study H — Health Score and forward-return association

For each chain, use the stored `health_scores` rows with version `v1` and
stored Binance `price_close_usd` closes. Score input dates, values, and
coverage are used as stored; the study does not recompute or modify Health
Score v1.

Create two fixed, calendar-spaced samples from the first stored score date for
that chain:

- 30-day sample: candidate score dates `first_score_date + k * 30 days`;
  forward return horizon is 30 days.
- 90-day sample: candidate score dates `first_score_date + k * 90 days`;
  forward return horizon is 90 days.

Keep a candidate only if that exact date has a v1 score and exact price closes
exist at both the candidate date and the candidate date plus the horizon.
Skipped candidates do not shift the calendar grid. The resulting valid
observations are non-overlapping within each horizon; report their `n` as
`n_independent`. Do not bridge gaps.

For each chain × horizon, report Spearman rank correlation between score and
forward return, its sample size, and an approximate two-sided 95% Fisher-z
interval. Compute `z=atanh(rho)`, standard error `1/sqrt(n_independent - 3)`,
and transform `z ± 1.959963984540054 * SE` back with `tanh`. The interval is
unavailable for `n_independent <= 3` or a correlation at an undefined
boundary; report the sample count and state that no interval is available.
This is an approximate interval for a rank correlation, not an exact
small-sample procedure.

For score terciles, process all chronological v1 score dates using expanding,
past-only cutoffs: at date `t`, compute type-7 one-third and two-thirds
quantiles from scores dated **strictly before** `t`. Require at least 30 prior
scores before assigning a tercile. Assign current scores `<= q1` to low,
`q1 < score <= q2` to middle, and `> q2` to high. Ties may make a group
smaller or empty; do not rebalance or use future scores. On the fixed
non-overlapping H-day sample, report the count, mean, and median forward return
for each assigned tercile. Exclude samples without 30 prior scores from these
tercile summaries and report those exclusions.

**Pre-registered reading rule:** an association is “not distinguishable from
zero” when its approximate 95% interval contains zero. If it does not contain
zero, report the measured association and interval without calling it
predictive. Never describe a score/return association as predictive. Score
inputs include price-derived market-condition components, so an association
may be mechanical momentum or mean-reversion rather than evidence from
on-chain information.

## Study R — regime v1 versus comparison state machine v2

Compute both state machines from the same chronologically ordered stored
`features` rows for `drawdown_365d`, `price_vs_sma200`, and `ret_90d`. Do not
change or persist the shipped regime table.

- **v1:** reproduce the shipped `scoring._raw_regime` priority and
  `scoring._regime_values` five-consecutive-calendar-day confirmation logic:
  stress when drawdown is `<= -0.50`, else uptrend when both price-vs-SMA200
  and 90-day return are positive, else downtrend when both are negative,
  else range. The first computed raw label initializes immediately; a raw
  label change is reported after five consecutive dates bearing that label.
  A date gap resets pending confirmation and starts a new observed duration.
- **v2:** use the identical raw classifier and date/gap handling, but enter
  stress immediately on the first raw-stress date. While reported as stress,
  exit only after five consecutive calendar dates with the same non-stress raw
  label. All non-stress-to-non-stress changes retain v1's five-day
  confirmation. A gap resets pending confirmation; no missing date counts
  toward entry or exit.

For each chain and state-machine version, report:

- number of reported regime switches (do not count initial state assignment);
- mean and median observed regime duration in consecutive computed calendar
  dates, including the final right-censored run and marking it as censored;
- number of reported regime episodes shorter than 10 observed days, designated
  “flip-flops” for this report only;
- per raw-stress episode, detection lag in calendar days from the first raw
  stress date to the first reported stress date, plus exit lag in calendar days
  from the last raw-stress date to the first subsequent reported non-stress
  date. An episode without a corresponding transition before the available
  data ends is reported as not detected or right-censored, not assigned an
  invented lag.

Raw-stress episodes are runs of consecutive calendar dates with an available
`drawdown_365d <= -0.50`; a gap or a non-stress/missing drawdown ends an
episode. A zero-day detection lag means entry on the first raw-stress date.
Report v1 and v2 side by side. V2 is a comparison only and is **not adopted**
by this prompt. Describe the potential trade-off—earlier stress entry versus
more switching—neutrally, based on the reported counts.

## Fixed data-quality caveats

- Maximum score-input coverage is BTC `0.70`, ETH `0.90`, SOL `0.60`, and BNB
  `0.60`; available inputs differ by chain.
- SOL price history starts in 2020-08. BNB price history starts in 2017-11,
  while its score history starts in 2022.
- A 365-day scenario horizon has only a handful of independent windows under
  the shipped availability rule. Its inferential calibration sample and
  confidence intervals may be especially limited.
- Crypto history spans only a few market regimes. All results are historical,
  sample-dependent descriptions, not a forecast or evidence of predictive
  accuracy.
- Source gaps, late score starts, partial score coverage, the Binance USDT
  price proxy, overlapping all-origin scenario outcomes, and approximate
  Fisher-z intervals constrain interpretation.

## Fixed output files

After the protocol commit, the read-only CLI writes deterministic reports:

- `docs/research/S.json` and `docs/research/S.md` — Study S outputs.
- `docs/research/H.json` and `docs/research/H.md` — Study H outputs.
- `docs/research/R.json` and `docs/research/R.md` — Study R outputs.
- `docs/RESEARCH.md` — result interpretation, limitations, and criteria that
  could change the interpretation.

The JSON records the protocol commit hash when available, method/version
identifiers, source date bounds and sample counts, metrics, intervals, and
exclusions. It contains no run timestamp, random seed, credentials, or raw
database dump. Markdown tables are generated from the same JSON values; a
repeat run against an unchanged database and code must produce byte-identical
study output.
