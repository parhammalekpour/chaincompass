# ChainCompass Free Data Audit

The measured audit feeds the SQLAlchemy/UTC-day data model described in
[ARCHITECTURE.md](ARCHITECTURE.md#data-layer). Binance USDT is a USD proxy,
not an independent fiat-USD observation.

Counts in this document are a dated snapshot; use `python -m app.ingest status`
for live numbers.

**Run date:** 2026-11-19

**Network condition:** Iran + VPN. Results may differ from a server abroad.

**Run duration:** 148.75 seconds. Requests were sequential, used
`ChainCompass-audit/0.1`, and used bounded history ranges.

## Reachability table

| Source | Probe | Reachable | Error class | HTTP | Latency |
|---|---|---|---|---:|---:|
| DefiLlama | Chain TVL, BTC/ETH/SOL/BSC TVL, stablecoin variants | Mixed | 404 or 200 | 200/404 |  |
| CoinGecko | Ping, current simple price, `/coins/markets` | Mixed | 429 stops source | 200/429 |  |
| Coin Metrics | Community catalog plus one-metric-per-call timeseries | Mixed | explicit 200/400/403 | 200/400/403 |  |
| mempool.space | Difficulty adjustment | No | HTTP status | 404 | 710 ms |
| mempool.space | 1-year hashrate endpoint | Yes | none | 200 | 678 ms |
| mempool.space | Recommended fees | Yes | none | 200 | 478 ms |
| Blockchain.info | 365-day BTC hashrate chart | Yes | none | 200 | 4636 ms |
| Blockchain.info | 30-day BTC TPS chart | Yes | none | 200 | 1096 ms |
| Blockchain.info | 30-day fees-per-transaction chart | No | HTTP status | 404 | 582 ms |
| Binance data-api | BTC/ETH/SOL/BNB 365-day klines | Yes | none | 200 | 935-4118 ms |
| Blockchair | BTC/ETH combined stats | Yes | none | 200 | 3436 ms |
| PublicNode | Ethereum RPC block-number sample | Yes | none | 200 | 4837 ms |
| Solana public RPC | Recent-performance sample | Yes | none | 200 | 2670 ms |
| BNB public RPC | BSC block-number sample | Yes | none | 200 | 4067 ms |

No DNS, TLS, or timeout errors occurred in the final live run. The
machine-readable JSON contains only schema, status, timing, and bounded-series
metadata; it does not contain raw API payloads.

## Coverage matrix

| Metric | BTC | ETH | SOL | BNB |
|---|---|---|---|---|
| Price | AVAILABLE — CoinGecko 365 days; Binance 365 days | AVAILABLE — CoinGecko 365 days; Binance 365 days | UNVERIFIED (CoinGecko 429; Binance 365-day probe) | UNVERIFIED (CoinGecko stopped; Binance 365-day probe) |
| Volume | AVAILABLE — CoinGecko 365 days; Binance 365 days | AVAILABLE — CoinGecko 365 days; Binance 365 days | AVAILABLE — Binance 365-day probe | AVAILABLE — Binance 365-day probe |
| Market cap | AVAILABLE — CoinGecko current and 365-day chart | AVAILABLE — CoinGecko current and 365-day chart | UNVERIFIED (CoinGecko 429) | UNVERIFIED (CoinGecko stopped) |
| Active addresses | AVAILABLE — Coin Metrics community AdrActCnt | AVAILABLE — Coin Metrics community AdrActCnt | UNVERIFIED (HTTP 403) | DISCONTINUED (legacy `bnb` ended 2019-04-22) |
| Tx count | AVAILABLE — Coin Metrics community TxCnt | AVAILABLE — Coin Metrics community TxCnt | UNVERIFIED (HTTP 403) | DISCONTINUED (legacy `bnb` ended 2019-04-22) |
| Network fees | AVAILABLE — BTC chart sources | UNVERIFIED (no aggregate source; RPC derivation high cost) | UNVERIFIED (no aggregate source; RPC derivation high cost) | UNVERIFIED (no aggregate source; RPC derivation high cost) |
| DEX volume | AVAILABLE — DefiLlama chain overview; unit UNVERIFIED; PROVISIONAL for Health Score (composition unverified) | AVAILABLE — DefiLlama, 2,939 complete days | AVAILABLE — DefiLlama, 1,871 complete days, 3 missing days | AVAILABLE — DefiLlama, 2,252 complete days |
| Protocol fees (not network fees) | AVAILABLE — DefiLlama, 1,953 complete days, 94 missing days; PROVISIONAL for Health Score (composition unverified) | AVAILABLE — DefiLlama, 3,154 complete days, 6 missing days | AVAILABLE — DefiLlama, 1,739 complete days | AVAILABLE — DefiLlama, 2,101 complete days |
| TVL | UNVERIFIED (DefiLlama BTC 404) | AVAILABLE — DefiLlama 3,341 points | AVAILABLE — DefiLlama 2,074 points | AVAILABLE — DefiLlama 2,212 points |
| Stablecoin supply | UNVERIFIED (DefiLlama BTC route 404) | AVAILABLE — DefiLlama 3,278 points | AVAILABLE — DefiLlama 1,654 points, 243 missing days | AVAILABLE — DefiLlama 2,223 points, 51 missing days |
| Hashrate/validators | AVAILABLE — mempool and Blockchain hash-rate | NOT APPLICABLE — PoS hashrate; validators UNVERIFIED | NOT APPLICABLE — PoS hashrate; validators UNVERIFIED | NOT APPLICABLE — PoS hashrate; validators UNVERIFIED |
| RPC liveness | AVAILABLE — mempool.space tip | AVAILABLE — PublicNode | AVAILABLE — Solana mainnet-beta | AVAILABLE — BSC dataseed |

`AVAILABLE` here describes a measured current series, not a claim that every
value is independently verified. DefiLlama's raw overview response does not
declare a unit; the daily values are numeric, but the USD unit remains
UNVERIFIED. DefiLlama protocol fees and protocol revenue are separate from
base/network transaction fees.

### Corrections

The DefiLlama Bitcoin DEX-volume and protocol-fee series remain stored, but
their aggregate composition has not been independently verified. They are
PROVISIONAL and excluded from Health Score candidates until verified. In
particular, the protocol-fees endpoint reports fees attributed to protocols
(including THORChain DEX and related services in this run), not Bitcoin
network/base transaction fees. The official API docs describe endpoint
contents but do not specify units; USD remains UNVERIFIED. The latest stored
data being numerically plausible against Binance volume is not unit evidence.
The BTC DEX breakdown is approximately 65% LN Exchange Spot and 35% Bisq;
the BTC protocol-fees breakdown is approximately 78% THORChain. Those totals
are ecosystem-activity proxies, not verified measures of Bitcoin chain usage.
Protocol fees on every chain are CONTEXT ONLY and are excluded from the Health
Score. BTC DEX volume is CONTEXT ONLY. ETH/SOL/BNB DEX volume is a low-weight
Health Score CANDIDATE; units remain UNVERIFIED-but-plausible, not confirmed
USD.

The ETH protocol-fees total is heterogeneous: the latest-30-day composition
includes liquid staking (Lido), block builders (Titan Builder), lending
(Aave), and stablecoin issuance (Ethena). As with other chain totals, it is
an ecosystem-activity proxy, not chain usage.

The earlier audit incorrectly treated Coin Metrics BNB market cap, active
addresses, and transactions as available because their requests returned HTTP
200. The bounded live probes on 2026-11-19 each returned zero points. The
Coin Metrics daily catalog reports `max_time=2019-04-22` for all three metrics,
so these are discontinued legacy `bnb` asset series, not current BNB Chain
coverage. The matrix and candidate-component table below now reflect that
evidence. Historical rows were still present in storage at this audit stage;
the 1,961 stored legacy BNB Coin Metrics observations have since been purged
explicitly. A subsequent `update --all` left zero BNB Coin Metrics observations
and preserved the discontinued coverage status. A new Coin Metrics Community
catalog probe for `bnb_bsc` also lists only `PriceUSD`; `AdrActCnt`, `TxCnt`,
`CapMrktCurUSD`, and `FeeTotUSD` are not present in the free catalog. This does
not change the legacy `bnb` conclusion or make BNB Chain on-chain metrics
available.

The historical TVL ranges measured in the live run start in 2017-09-27 for
ETH, 2021-03-17 for SOL, and 2020-10-30 for BNB. The global stablecoin chart
has 3278 points from 2017-11-29 to 2026-11-19 with no missing days.

## Source license and terms

| Source | Terms link | Attribution or legal status |
|---|---|---|
| DefiLlama | https://defillama.com/terms | Preserve attribution; review terms before redistribution |
| CoinGecko | https://www.coingecko.com/en/api_terms | Attribution required by its free API terms |
| Coin Metrics | https://coinmetrics.io/terms/ | Attribution required; Community API data is non-commercial |
| mempool.space | https://mempool.space/docs/api/rest | Preserve attribution; review rate-limit and redistribution terms |
| Blockchain.info | https://www.blockchain.com/legal/privacy | Preserve attribution; chart/API terms require review |
| Binance data-api | https://data-api.binance.vision/ | UNVERIFIED; redistribution terms require review |
| Blockchair | https://blockchair.com/api/docs | UNVERIFIED; free-plan limits and attribution require review |
| PublicNode | https://www.publicnode.com/terms | UNVERIFIED; public RPC terms apply |
| Solana public RPC | https://solana.com/terms | UNVERIFIED; public infrastructure terms apply |
| BNB public RPC | https://www.bnbchain.org/en/terms | UNVERIFIED; public endpoint terms apply |

## Rate-limit notes

- Live requests were sequential with a 1-second pause and at most one retry
  for timeout/transport failures.
-     CoinGecko returned 429 for the SOL 365-day chart. This response supplied
  `x-ratelimit-limit: 2`, `x-ratelimit-remaining: 0`, and an
  `x-ratelimit-reset` timestamp, but no `Retry-After` header. The audit stopped
  further CoinGecko probes, including BNB.
- DefiLlama, Binance, and CoinGecko market histories were bounded.
- No other source returned a 429 in this run.

## Decision summary

- Score-eligible inputs in the registry are Binance `price_close_usd` and
  `volume_usd` for all four chains; Coin Metrics `active_addresses` and
  `tx_count` for BTC/ETH; DefiLlama TVL, stablecoin supply, and DEX volume for
  ETH/SOL/BNB; and BTC hashrate plus derived BTC `fees_usd`. The Health Score
  itself is now implemented as version `v1`; these registered inputs describe
  eligibility, not a claim that every chain has every component.
- Context-only inputs are Coin Metrics and CoinGecko market cap, DefiLlama
  protocol fees on every chain, and BTC DefiLlama DEX volume. Protocol fees
  describe ecosystem activity, not network fees.
- BTC DefiLlama `tvl_usd`/`stablecoin_supply_usd` and SOL Coin Metrics
  `active_addresses`, `tx_count`, and `market_cap_usd` are unavailable; legacy
  BNB Coin Metrics `market_cap_usd`, `active_addresses`, and `tx_count` are
  discontinued. Gaps remain missing and are not imputed.
- DefiLlama units remain UNVERIFIED. ETH/SOL/BNB DEX volume is a low-weight
  score candidate with units UNVERIFIED-but-plausible; all protocol fees and
  BTC DEX volume remain context-only.

## History depth versus probe window

| Source | BTC depth | ETH depth | SOL depth | BNB depth | Probe window |
|---|---|---|---|---|---|
| Binance data-api | earliest 2017-08-17; ~9.26 years | earliest 2017-08-17; ~9.26 years | earliest 2020-08-11; ~6.27 years | earliest 2017-11-06; ~9.04 years | 365 daily candles |
| DefiLlama TVL | BTC endpoint 404 | earliest 2017-09-27; ~9.15 years | earliest 2021-03-17; ~5.68 years | earliest 2020-10-30; ~6.06 years | full measured series / bounded probe variants |
| DefiLlama stablecoins | BTC route 404 | earliest 2017-11-29; ~8.97 years | earliest 2021-09-10; ~5.19 years | earliest 2020-08-29; ~6.23 years | full measured series |
| mempool/Blockchain BTC | 365-day or 1-year bounded measured history | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | 365d/1y/30d |
| Coin Metrics | requested 2025-11-20 to 2026-11-19 window | requested 2025-11-20 to 2026-11-19 window | requested 2025-11-20 to 2026-11-19 window | requested 2025-11-20 to 2026-11-19 window | 1d window; one metric per call |

## Targeted BNB Chain and DefiLlama chain analytics probes

The targeted probes used `ChainCompass-audit/0.1`, sequential requests, a
one-second pause, and a 30-day Coin Metrics window (2026-10-20 through
2026-11-19). Audit requests were repeated only for the BNB Chain catalog
endpoint to capture all metric frequency ranges; the complete targeted run
took 64.24 seconds including that catalog verification.

Coin Metrics Community's `bnb_bsc` catalog response (HTTP 200) listed this
complete metric/frequency range:

| Asset | Metric | Frequency | First | Last |
|---|---|---|---|---|
| `bnb_bsc` | PriceUSD | 1d | 2020-08-29 | 2026-11-18 |

The catalog contains no `AdrActCnt`, `TxCnt`, `CapMrktCurUSD`, or `FeeTotUSD`
entry for `bnb_bsc`. Each was requested separately:

| Asset | Metric | HTTP | Points | Last point | Evidence and label |
|---|---|---:|---:|---|---|
| `bnb_bsc` | AdrActCnt | 403 | — | — | Catalog confirms absent; NOT AVAILABLE FREE |
| `bnb_bsc` | TxCnt | 403 | — | — | Catalog confirms absent; NOT AVAILABLE FREE |
| `bnb_bsc` | CapMrktCurUSD | 400 | — | — | Catalog confirms absent; NOT AVAILABLE FREE |
| `bnb_bsc` | FeeTotUSD | 403 | — | — | Catalog confirms absent; NOT AVAILABLE FREE |

The `sol` catalog included `PriceUSD`, `CapMrktEstUSD`, reference-rate metrics,
and spot-volume data, but none of the four requested metrics
(`AdrActCnt`, `TxCnt`, `CapMrktCurUSD`, `FeeTotUSD`).

DefiLlama endpoint documentation identifies `/overview/dexs/{chain}` as
chain-filtered DEX volume and `/overview/fees/{chain}` as chain-filtered
protocol fees/revenue; the fees endpoint accepts separate `dailyFees` and
`dailyRevenue` types. The aggregate response's `totalDataChart` contains
numeric daily values but has no explicit unit field. Therefore USD units are
UNVERIFIED. Protocol fees mean fees paid to protocols; they are not network or
base transaction fees. Revenue is recorded separately and is not substituted
for fees. See the [DefiLlama free API documentation](https://api-docs.defillama.com/llms-free.txt).

All dates below exclude the current incomplete UTC day (2026-11-19); latest
complete date is 2026-11-18. “Missing days” counts omitted dates between the
first and last points; no values are filled.

| Chain | Series | Endpoint | HTTP | First | Last complete | Points | Missing days | Unit | Semantics |
|---|---|---|---:|---|---|---:|---:|---|---|
| ETH | DEX volume | `https://api.llama.fi/overview/dexs/ethereum?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true` | 200 | 2018-11-02 | 2026-11-18 | 2,939 | 0 | UNVERIFIED | Chain-filtered aggregate DEX trading volume |
| ETH | Protocol fees (`dailyFees`) | `https://api.llama.fi/overview/fees/ethereum?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=dailyFees` | 200 | 2018-03-26 | 2026-11-18 | 3,154 | 6 | UNVERIFIED | Fees paid to protocols; not network fees |
| ETH | Protocol revenue (`dailyRevenue`) | `https://api.llama.fi/overview/fees/ethereum?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue` | 200 | 2018-03-26 | 2026-11-18 | 3,154 | 6 | UNVERIFIED | Protocol revenue; separate from fees |
| SOL | DEX volume | `https://api.llama.fi/overview/dexs/solana?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true` | 200 | 2021-10-02 | 2026-11-18 | 1,871 | 3 | UNVERIFIED | Chain-filtered aggregate DEX trading volume |
| SOL | Protocol fees (`dailyFees`) | `https://api.llama.fi/overview/fees/solana?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=dailyFees` | 200 | 2022-02-14 | 2026-11-18 | 1,739 | 0 | UNVERIFIED | Fees paid to protocols; not network fees |
| SOL | Protocol revenue (`dailyRevenue`) | `https://api.llama.fi/overview/fees/solana?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue` | 200 | 2022-02-14 | 2026-11-18 | 1,739 | 0 | UNVERIFIED | Protocol revenue; separate from fees |
| BNB/BSC | DEX volume | `https://api.llama.fi/overview/dexs/bsc?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true` | 200 | 2020-09-19 | 2026-11-18 | 2,252 | 0 | UNVERIFIED | Chain-filtered aggregate DEX trading volume |
| BNB/BSC | Protocol fees (`dailyFees`) | `https://api.llama.fi/overview/fees/bsc?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=dailyFees` | 200 | 2021-02-17 | 2026-11-18 | 2,101 | 0 | UNVERIFIED | Fees paid to protocols; not network fees |
| BNB/BSC | Protocol revenue (`dailyRevenue`) | `https://api.llama.fi/overview/fees/bsc?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue` | 200 | 2021-02-17 | 2026-11-18 | 2,101 | 0 | UNVERIFIED | Protocol revenue; separate from fees |
| BTC | DEX volume | `https://api.llama.fi/overview/dexs/bitcoin?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true` | 200 | 2014-02-17 | 2026-11-18 | 4,507 | 151 | UNVERIFIED | Chain-filtered aggregate DEX trading volume |
| BTC | Protocol fees (`dailyFees`) | `https://api.llama.fi/overview/fees/bitcoin?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=dailyFees` | 200 | 2021-04-12 | 2026-11-18 | 1,953 | 94 | UNVERIFIED | Fees paid to protocols; not network fees |
| BTC | Protocol revenue (`dailyRevenue`) | `https://api.llama.fi/overview/fees/bitcoin?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue` | 200 | 2021-04-12 | 2026-11-18 | 1,840 | 207 | UNVERIFIED | Protocol revenue; separate from fees |

## Primary and fallback decisions

- **Primary BTC/ETH/SOL/BNB price and volume:** Binance daily klines. Fallback:
  CoinGecko current/simple price and available market charts; the latest live
  run stopped CoinGecko after 429.
- **Primary BTC active addresses and tx count:** Coin Metrics community
  `AdrActCnt` and `TxCnt`, both 200. Fallback: UNVERIFIED until another source
  is cataloged.
- **Primary ETH active addresses and tx count:** Coin Metrics community
  `AdrActCnt` and `TxCnt`, both 200. Fee remains UNVERIFIED by explicit 403.
- **Primary SOL metrics:** Coin Metrics PriceUSD 200; active addresses, tx
  count, and fees are UNVERIFIED explicit 403/400. No free aggregate source was
  found in this audit.
- **BNB market cap, active addresses, and tx count:** Coin Metrics legacy `bnb`
  series are DISCONTINUED (catalog max date 2019-04-22; bounded 2025-11-20 to
  2026-11-19 requests returned HTTP 200 with zero points). These do not
  represent current BNB Chain metrics; no current aggregate replacement was
  verified. Binance price and volume remain available. Hashrate is NOT
  APPLICABLE for PoS.
- **Primary ETH/SOL/BNB TVL and stablecoin supply:** DefiLlama.
- **DEX volume and protocol fees:** DefiLlama chain analytics have measured
  daily history for ETH, SOL, and BSC. The response omits units, and protocol
  fees are not network fees; consider as USD-derived candidate data only after
  resolving unit metadata. `dailyRevenue` remains a separate series.
- **Primary BTC hashrate:** Blockchain.info daily hash-rate chart, converted
  from TH/s to H/s; mempool.space remains a shorter-history fallback.
- **Primary BTC fees:** Blockchain.info daily `transaction-fees` chart, converted
  from BTC to USD with the same-day Binance BTC close. mempool.space's
  recommended-fee endpoint is a current fee-rate measure, not a daily total.

## Network Health Score candidate components

| Component | BTC | ETH | SOL | BNB | Source | History depth | Status |
|---|---|---|---|---|---|---|---|
| Price | AVAILABLE | AVAILABLE | AVAILABLE via Binance | AVAILABLE via Binance | Binance klines | BTC/ETH/SOL/BNB earliest candles 2017-2020 | computable now |
| Volume | AVAILABLE | AVAILABLE | AVAILABLE via Binance | AVAILABLE via Binance | Binance klines | BTC/ETH/SOL/BNB earliest candles 2017-2020 | computable now |
| Market cap | AVAILABLE | AVAILABLE | UNVERIFIED (HTTP 403) | DISCONTINUED (legacy `bnb`; last 2019-04-22) | Coin Metrics Community | BTC/ETH current; legacy BNB through 2019-04-22 | not computable for current BNB Chain |
| Active addresses | AVAILABLE | AVAILABLE | UNVERIFIED (HTTP 403) | DISCONTINUED (legacy `bnb`; last 2019-04-22) | Coin Metrics Community | BTC/ETH current; legacy BNB through 2019-04-22 | not computable for current BNB Chain |
| Tx count | AVAILABLE | AVAILABLE | UNVERIFIED (HTTP 403) | DISCONTINUED (legacy `bnb`; last 2019-04-22) | Coin Metrics Community | BTC/ETH current; legacy BNB through 2019-04-22 | not computable for current BNB Chain |
| Network fees | AVAILABLE | UNVERIFIED | UNVERIFIED | UNVERIFIED | Blockchain.info fees converted with Binance BTC close | 2017-08-17 to 2026-11-18 | computable now for BTC only |
| DEX volume | CONTEXT ONLY (about 65% LN Exchange Spot, 35% Bisq) | CANDIDATE (low weight; unit UNVERIFIED-but-plausible) | CANDIDATE (low weight; unit UNVERIFIED-but-plausible; 3 missing days) | CANDIDATE (low weight; unit UNVERIFIED-but-plausible) | DefiLlama chain overview | BTC 2014-02-17; ETH 2018-11-02; SOL 2021-10-02; BSC 2020-09-19 | BTC excluded; other chains need methodology validation |
| Protocol fees (not network fees) | CONTEXT ONLY (about 78% THORChain; not network fees) | CONTEXT ONLY (heterogeneous ecosystem activity; 6 missing days) | CONTEXT ONLY | CONTEXT ONLY | DefiLlama `dailyFees` | BTC 2021-04-12; ETH 2018-03-26; SOL 2022-02-14; BSC 2021-02-17 | Excluded from Health Score; never substitute for network fees |
| TVL | UNVERIFIED (HTTP 404; not proof of absence) | AVAILABLE | AVAILABLE | AVAILABLE | DefiLlama | stored ranges below | computable now for ETH/SOL/BNB |
| Stablecoin supply | UNVERIFIED (HTTP 404; not proof of absence) | AVAILABLE | AVAILABLE with gaps | AVAILABLE with gaps | DefiLlama | stored ranges below | computable with explicit gaps |
| Hashrate | AVAILABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | Blockchain.info (TH/s converted to H/s) | 2017-01-01 to 2026-11-18 | computable now for BTC |
| Validators | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED until dedicated free source | none measured | needs more research |

Missing components remain unavailable and must not be imputed.

## What ingestion actually stored

**Measured run:** 2026-11-19, Iran + VPN. `last_date` is the latest complete
UTC day available at the run (`2026-11-18`). Where the first stored date equals
the requested `--since 2017-01-01`, it is reported as `>=2017-01-01`, not as a
proven source start. Point counts are stored observation counts; missing days
are not filled. After the confirmed legacy-BNB purge, DefiLlama analytics backfill, and
successful `update --all`, the database contains 87,738 observations. The
follow-up update rewrote overlap rows without increasing the total.

| Chain | Metric | Source | First stored date | Last stored date | Points | Missing days | Status |
|---|---|---|---|---|---:|---:|---|
| BTC | Market cap snapshot | CoinGecko | 2026-11-18 | 2026-11-18 | 1 | 0 | approximate snapshot; context/cross-check only |
| ETH | Market cap snapshot | CoinGecko | 2026-11-18 | 2026-11-18 | 1 | 0 | approximate snapshot; context/cross-check only |
| SOL | Market cap snapshot | CoinGecko | 2026-11-18 | 2026-11-18 | 1 | 0 | approximate snapshot; context/cross-check only |
| BNB | Market cap snapshot | CoinGecko | 2026-11-18 | 2026-11-18 | 1 | 0 | approximate snapshot; context/cross-check only |
| BTC | Market cap | Coin Metrics Community | >=2017-01-01 | 2026-11-18 | 3609 | 0 | ok |
| BTC | Active addresses | Coin Metrics Community | >=2017-01-01 | 2026-11-18 | 3609 | 0 | ok |
| BTC | Transactions | Coin Metrics Community | >=2017-01-01 | 2026-11-18 | 3609 | 0 | ok |
| BTC | Hashrate (H/s) | Blockchain.info | >=2017-01-01 | 2026-11-18 | 3606 | 3 | ok |
| BTC | Fees (USD, derived) | Blockchain.info + Binance close conversion | 2017-08-17 | 2026-11-18 | 3378 | 3 | ok; 228 fee rows without a matching close omitted |
| ETH | Market cap | Coin Metrics Community | >=2017-01-01 | 2026-11-18 | 3609 | 0 | ok |
| ETH | Active addresses | Coin Metrics Community | >=2017-01-01 | 2026-11-18 | 3609 | 0 | ok |
| ETH | Transactions | Coin Metrics Community | >=2017-01-01 | 2026-11-18 | 3609 | 0 | ok |
| ETH | TVL | DefiLlama | 2017-09-27 | 2026-11-18 | 3340 | 0 | ok |
| ETH | Stablecoin supply | DefiLlama | 2017-11-29 | 2026-11-18 | 3277 | 0 | ok |
| SOL | Market cap, active addresses, transactions | Coin Metrics Community | — | — | 0 | 0 | unavailable (HTTP 403) |
| SOL | TVL | DefiLlama | 2021-03-17 | 2026-11-18 | 2073 | 0 | ok |
| SOL | Stablecoin supply | DefiLlama | 2021-09-10 | 2026-11-18 | 1653 | 243 | ok; gap preserved |
| BNB | Market cap | Coin Metrics Community | — | — | 0 | 0 | discontinued; legacy asset ended 2019-04-22, purged |
| BNB | Active addresses | Coin Metrics Community | — | — | 0 | 0 | discontinued; legacy asset ended 2019-04-22, purged |
| BNB | Transactions | Coin Metrics Community | — | — | 0 | 0 | discontinued; legacy asset ended 2019-04-22, purged |
| BNB | TVL | DefiLlama | 2020-10-30 | 2026-11-18 | 2211 | 0 | ok |
| BNB | Stablecoin supply | DefiLlama | 2020-08-29 | 2026-11-18 | 2222 | 51 | ok; gap preserved |
| BTC | DEX volume | DefiLlama | >=2017-01-01 | 2026-11-18 | 3609 | 0 | ok; unit UNVERIFIED |
| BTC | Protocol fees | DefiLlama | 2021-04-12 | 2026-11-18 | 1953 | 94 | ok; unit UNVERIFIED; not network fees |
| ETH | DEX volume | DefiLlama | 2018-11-02 | 2026-11-18 | 2939 | 0 | ok; unit UNVERIFIED |
| ETH | Protocol fees | DefiLlama | 2018-03-26 | 2026-11-18 | 3154 | 6 | ok; unit UNVERIFIED; not network fees |
| SOL | DEX volume | DefiLlama | 2021-10-02 | 2026-11-18 | 1871 | 3 | ok; unit UNVERIFIED |
| SOL | Protocol fees | DefiLlama | 2022-02-14 | 2026-11-18 | 1739 | 0 | ok; unit UNVERIFIED; not network fees |
| BNB (BSC) | DEX volume | DefiLlama | 2020-09-19 | 2026-11-18 | 2252 | 0 | ok; unit UNVERIFIED |
| BNB (BSC) | Protocol fees | DefiLlama | 2021-02-17 | 2026-11-18 | 2101 | 0 | ok; unit UNVERIFIED; not network fees |

DefiLlama stablecoin supply has two known multi-day gaps: SOL
2021-09-11 through 2022-05-11 (243 days), and BNB 2020-08-30 through
2020-10-19 (51 days). BTC hashrate and fees each have three missing days in
their stored ranges; these remain gaps. BTC DefiLlama protocol-fee gaps longer
than three days are 2021-07-08 through 2021-07-13 (6 days), 2021-07-17 through
2021-09-28 (74 days), 2021-11-13 through 2021-11-17 (5 days), and 2023-05-08
through 2023-05-12 (5 days); these are reported, not filled. The other
DefiLlama analytics gaps are shorter than four consecutive days. BTC hashrate
on 2026-11-18 was approximately `1.0522e21 H/s`; ETH TVL on 2021-11-09 was
`$107.424B`.

DefiLlama DEX-volume and `dailyFees` protocol-fee observations passed the
minimum 365-day history, recent-complete-day, and Decimal checks for BTC, ETH,
SOL, and BSC. The BTC DEX backfill begins at the requested 2017-01-01 floor;
this is not evidence that the source begins on that date. No values were
forward-filled. The API response does not declare a unit, so these rows remain
unit-UNVERIFIED and must not be used as confirmed USD amounts. Protocol fees
are fees paid to protocols, not network/base transaction fees, and are stored
under `protocol_fees_usd`, never `fees_usd`. No BNB Chain Coin Metrics on-chain
series were ingested: the `bnb_bsc` catalog lacks the requested metrics.

### CoinGecko worker snapshot

The worker's live `/api/v3/coins/markets` request succeeded at
`2026-11-19T20:52:21.994947Z` (HTTP 200), producing four positive market-cap
observations for BTC, ETH, SOL, and BNB under the separate `coingecko` source,
all labeled `obs_date=2026-11-18`. This is a forward-collected snapshot, not
historical coverage; the earlier audit's CoinGecko chart 429 remains a valid
result for that different request.
CoinGecko market-cap snapshots are approximate values collected forward from
the first run. They are used only for cross-checks/context, never as Health
Score inputs. A manual `--once` run during the UTC day stores an intraday
value under the previous UTC date; that is a date-label convention, not a
true end-of-day capture.

### DefiLlama composition, unit evidence, and BTC shape

On 2026-11-19 UTC, read-only calls to the same `/overview/dexs/{chain}` and
`/overview/fees/{chain}?dataType=dailyFees` endpoints used by ingestion set
`excludeTotalDataChartBreakdown=false`. Shares below are each protocol's sum
divided by the sum of the returned protocol breakdown over the latest 30
complete UTC days (2026-10-20 through 2026-11-18); rounded to 0.01%. This
describes the API's breakdown, not an independent completeness audit.

| Chain | Series | Top protocol contributions |
|---|---|---|
| BTC | DEX volume | LN Exchange Spot 64.78%; Bisq 35.00%; Counterparty DEX 0.22% |
| BTC | Protocol fees | THORChain DEX 78.51%; Relay 12.18%; THORSwap 6.49%; Liquidium WTF 2.61%; Garden 0.13% |
| ETH | DEX volume | Uniswap V4 30.47%; Uniswap V3 26.43%; Fluid DEX 8.94%; Curve DEX 7.76%; Metric V1 5.76% |
| ETH | Protocol fees | Lido 14.29%; Titan Builder 9.59%; Aave V3 8.40%; Sky Lending 7.29%; Ethena USDe 4.90% |
| SOL | DEX volume | Orca DEX 13.08%; PumpSwap 12.80%; BisonFi 12.05%; Raydium AMM 8.79%; Meteora DLMM 7.35% |
| SOL | Protocol fees | PumpSwap 23.80%; pump.fun 14.74%; Axiom 5.74%; Meteora DLMM 5.44%; Collector Crypt 3.80% |
| BSC | DEX volume | PancakeSwap AMM V3 55.03%; PancakeSwap Infinity 15.94%; Metric V1 8.04%; Uniswap V3 4.59%; PancakeSwap AMM 3.69% |
| BSC | Protocol fees | Flap sh 30.33%; Predict Fun 13.93%; PancakeSwap AMM V3 10.86%; PancakeSwap AMM 4.85%; GMGN 4.77% |

BTC DEX-volume rows contain zero zero-value days; their median daily value is
161,095 and maximum is 13,684,389. The first 30-consecutive-nonzero-day run
starts 2014-07-17. BTC protocol-fee rows likewise contain zero zero-value days;
median is 14,415, maximum is 323,444, and the first 30-day nonzero run starts
2021-04-12. For 2021-07-17 through 2021-09-28, all 74 dates are absent from
both `totalDataChart` and `totalDataChartBreakdown`; the raw response has no
null or zero placeholders for those dates.

The official [DefiLlama API documentation](https://api-docs.defillama.com/llms-free.txt)
was reachable. It describes `/overview/dexs/{chain}` as listing DEXs and
volume summaries, and `/overview/fees/{chain}` as listing protocol fee and
revenue summaries. It does not declare a currency/unit for the chart values.
Therefore the data's unit remains **UNVERIFIED**, not AVAILABLE as USD.
For scale context only, stored median values over 2025-11-19 through
2026-11-18 compare as follows:

| Chain | DefiLlama DEX median | DefiLlama protocol-fees median | Binance native-coin quote-volume median | Scale assessment |
|---|---:|---:|---:|---|
| ETH | 1,349,970,369.52 | 10,391,653.04 | 674,850,744.71 | UNVERIFIED but plausible relative scale |
| SOL | 2,416,266,699.16 | 9,136,232.49 | 231,023,182.06 | UNVERIFIED but plausible relative scale |
| BSC | 1,036,102,504.54 | 1,596,017.71 | 81,086,718.40 | UNVERIFIED but plausible relative scale |

These are stored-value medians, not verified USD measurements. The Binance
comparison is only a rough scale reference and cannot establish the DefiLlama
unit or completeness.

### Trailing-median outliers before sparse-series suppression

The pre-change `check` counted 208 observations outside 10x/0.1x of their
trailing 30-day median. “Typical median” below is the median of those outlier
events' trailing medians; DefiLlama values are in unverified source units.
None of the 208 events had a zero-median baseline or at least 10 zero values
in its preceding 30-day window. One event had a baseline at or below 1; three
were at or below 10. The new rule suppresses only zero-median windows and
windows containing at least 10 zero observations, leaving these measured
events unchanged.
These 208 alerts are informational, not conclusions about bad data. One
possible explanation is that DefiLlama chain totals change composition as
protocols are listed or delisted; this is a hypothesis, not verified
causation. Any future Health Score use should use robust statistics such as
medians and quantiles rather than raw point changes or outlier counts.

| Chain | Metric | Outlier count | Typical trailing median |
|---|---|---:|---:|
| BNB | DEX volume | 7 | 2,277 |
| BNB | Protocol fees | 16 | 23,410.25 |
| BNB | Binance quote volume | 10 | 19,814,620.09 |
| BTC | DEX volume | 56 | 52,323.50 |
| BTC | Protocol fees | 21 | 3,399 |
| BTC | Binance quote volume | 1 | 308,553,476.71 |
| ETH | DEX volume | 7 | 51,779 |
| ETH | Protocol fees | 13 | 60 |
| ETH | Binance quote volume | 1 | 167,318,428.66 |
| SOL | DEX volume | 51 | 207,274 |
| SOL | Protocol fees | 16 | 2,513 |
| SOL | Binance quote volume | 9 | 48,653,738.99 |

The Coin Metrics BNB history stopped at 2019-04-22; all 1,961 legacy rows were
purged, and the three corresponding coverage rows remain `discontinued` after
the live update. SOL's requested Coin Metrics metrics returned HTTP 403 and
are stored as unavailable. Coin Metrics Community data is non-commercial and
requires attribution.

### RPC liveness probes

A live, sequential `rpc_probe` run completed on 2026-11-20. Each request used
the configured 10-second timeout, one attempt, and a ChainCompass User-Agent.
All four chain probes succeeded. This establishes only a point-in-time RPC
liveness observation, not historical coverage or a guarantee of provider
availability. BTC's tip-height endpoint does not supply a block timestamp, so
its block age is not applicable. URLs and response bodies are intentionally
not stored.

| Chain | Provider label | Result | Latency (ms) | Height / slot | Block age (s) | Checked at (UTC) |
|---|---|---:|---:|---:|---:|---|
| BTC | mempool.space | ok | 3532 | 976726 | — | 2026-11-20 12:54:12 |
| ETH | publicnode | ok | 581 | 26456435 | 2 | 2026-11-20 12:54:13 |
| SOL | solana-mainnet-beta | ok | 1018 | 471744543 | 0 | 2026-11-20 12:54:15 |
| BNB | bsc-dataseed | ok | 1878 | 134698690 | 0 | 2026-11-20 12:54:18 |
