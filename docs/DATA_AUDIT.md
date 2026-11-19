# ChainCompass Free Data Audit

The measured audit feeds the SQLAlchemy/UTC-day data model described in
[ARCHITECTURE.md](ARCHITECTURE.md#data-layer). Binance USDT is a USD proxy,
not an independent fiat-USD observation.

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
| Price | CoinGecko 365 days; Binance 365 days | CoinGecko 365 days; Binance 365 days | CoinGecko 429 stopped daily chart; Binance 365 days | CoinGecko unprobed; Binance 365 days |
| Volume | CoinGecko 365 days; Binance 365 days | CoinGecko 365 days; Binance 365 days | CoinGecko 429 stopped; Binance 365 days | Binance 365 days; CoinGecko unprobed |
| Market cap | CoinGecko current and 365-day chart | CoinGecko current and 365-day chart | CoinGecko daily UNVERIFIED after 429 | CoinGecko UNPROBED |
| Active addresses | AVAILABLE — Coin Metrics community AdrActCnt 200 | AVAILABLE — Coin Metrics community AdrActCnt 200 | UNVERIFIED (403; no aggregate source) | AVAILABLE — Coin Metrics community AdrActCnt 200 |
| Tx count | AVAILABLE — Coin Metrics community TxCnt 200 | AVAILABLE — Coin Metrics community TxCnt 200 | UNVERIFIED (403; no aggregate source) | AVAILABLE — Coin Metrics community TxCnt 200 |
| Fees | AVAILABLE — mempool and Blockchain transaction-fees variant; Coin Metrics FeeTotUSD 403 | UNVERIFIED (403; no aggregate source) | UNVERIFIED (403; no aggregate source) | UNVERIFIED (400; unsupported 1d community metric) |
| TVL | UNVERIFIED (DefiLlama BTC 404) | AVAILABLE — DefiLlama 3341 points | AVAILABLE — DefiLlama 2074 points | AVAILABLE — DefiLlama 2212 points |
| Stablecoin supply | UNVERIFIED (DefiLlama BTC route 404) | AVAILABLE — DefiLlama 3278 points | AVAILABLE — DefiLlama 1654 points, 243 gaps | AVAILABLE — DefiLlama 2223 points, 51 gaps |
| Hashrate/validators | AVAILABLE — mempool and Blockchain hash-rate | NOT APPLICABLE — PoS hashrate; validators UNVERIFIED | NOT APPLICABLE — PoS hashrate; validators UNVERIFIED | NOT APPLICABLE — PoS hashrate; validators UNVERIFIED |

### Corrections

The earlier audit incorrectly treated Coin Metrics BNB market cap, active
addresses, and transactions as available because their requests returned HTTP
200. The bounded live probes on 2026-11-19 each returned zero points. The
Coin Metrics daily catalog reports `max_time=2019-04-22` for all three metrics,
so these are discontinued legacy `bnb` asset series, not current BNB Chain
coverage. The matrix and candidate-component table below now reflect that
evidence. Historical rows were still present in storage at this audit stage;
they are handled separately by the ingestion correction.

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

## DECISION

## History depth versus probe window

| Source | BTC depth | ETH depth | SOL depth | BNB depth | Probe window |
|---|---|---|---|---|---|
| Binance data-api | earliest 2017-08-17; ~9.26 years | earliest 2017-08-17; ~9.26 years | earliest 2020-08-11; ~6.27 years | earliest 2017-11-06; ~9.04 years | 365 daily candles |
| DefiLlama TVL | BTC endpoint 404 | earliest 2017-09-27; ~9.15 years | earliest 2021-03-17; ~5.68 years | earliest 2020-10-30; ~6.06 years | full measured series / bounded probe variants |
| DefiLlama stablecoins | BTC route 404 | earliest 2017-11-29; ~8.97 years | earliest 2021-09-10; ~5.19 years | earliest 2020-08-29; ~6.23 years | full measured series |
| mempool/Blockchain BTC | 365-day or 1-year bounded measured history | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | 365d/1y/30d |
| Coin Metrics | requested 2025-11-20 to 2026-11-19 window | requested 2025-11-20 to 2026-11-19 window | requested 2025-11-20 to 2026-11-19 window | requested 2025-11-20 to 2026-11-19 window | 1d window; one metric per call |

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
| Market cap | AVAILABLE | AVAILABLE | UNAVAILABLE (403) | DISCONTINUED (legacy `bnb`; last 2019-04-22) | Coin Metrics Community | BTC/ETH current; BNB through 2019-04-22 | not computable for current BNB Chain |
| Active addresses | AVAILABLE | AVAILABLE | UNAVAILABLE (403) | DISCONTINUED (legacy `bnb`; last 2019-04-22) | Coin Metrics Community | BTC/ETH current; BNB through 2019-04-22 | not computable for current BNB Chain |
| Tx count | AVAILABLE | AVAILABLE | UNAVAILABLE (403) | DISCONTINUED (legacy `bnb`; last 2019-04-22) | Coin Metrics Community | BTC/ETH current; BNB through 2019-04-22 | not computable for current BNB Chain |
| Fees | AVAILABLE | UNVERIFIED | UNVERIFIED | UNVERIFIED | Blockchain.info fees converted with Binance BTC close | 2017-08-17 to 2026-11-18 | computable now for BTC only |
| TVL | UNAVAILABLE (prior HTTP 404) | AVAILABLE | AVAILABLE | AVAILABLE | DefiLlama | stored ranges below | computable now for ETH/SOL/BNB |
| Stablecoin supply | UNAVAILABLE (prior HTTP 404) | AVAILABLE | AVAILABLE with 243 gaps | AVAILABLE with 51 gaps | DefiLlama | stored ranges below | computable with explicit gaps |
| Hashrate | AVAILABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | Blockchain.info (TH/s converted to H/s) | 2017-01-01 to 2026-11-18 | computable now for BTC |
| Validators | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED until dedicated free source | none measured | needs more research |

Missing components remain unavailable and must not be imputed.

## What ingestion actually stored

**Measured run:** 2026-11-19, Iran + VPN. `last_date` is the latest complete
UTC day available at the run (`2026-11-18`). Where the first stored date equals
the requested `--since 2017-01-01`, it is reported as `>=2017-01-01`, not as a
proven source start. Point counts are stored observation counts; missing days
are not filled.

| Chain | Metric | Source | First stored date | Last stored date | Points | Missing days | Status |
|---|---|---|---|---|---:|---:|---|
| BTC | Market cap | Coin Metrics Community | >=2017-01-01 | 2026-11-18 | 3609 | 0 | ok |
| BTC | Active addresses | Coin Metrics Community | >=2017-01-01 | 2026-11-18 | 3609 | 0 | ok |
| BTC | Transactions | Coin Metrics Community | >=2017-01-01 | 2026-11-18 | 3609 | 0 | ok |
| BTC | Hashrate (H/s) | Blockchain.info | >=2017-01-01 | 2026-11-18 | 3606 | 3 | ok |
| BTC | Fees (USD) | Blockchain.info + Binance close conversion | 2017-08-17 | 2026-11-18 | 3378 | 3 | ok |
| ETH | Market cap | Coin Metrics Community | >=2017-01-01 | 2026-11-18 | 3609 | 0 | ok |
| ETH | Active addresses | Coin Metrics Community | >=2017-01-01 | 2026-11-18 | 3609 | 0 | ok |
| ETH | Transactions | Coin Metrics Community | >=2017-01-01 | 2026-11-18 | 3609 | 0 | ok |
| ETH | TVL | DefiLlama | 2017-09-27 | 2026-11-18 | 3340 | 0 | ok |
| ETH | Stablecoin supply | DefiLlama | 2017-11-29 | 2026-11-18 | 3277 | 0 | ok |
| SOL | Market cap, active addresses, transactions | Coin Metrics Community | — | — | 0 | 0 | unavailable (HTTP 403) |
| SOL | TVL | DefiLlama | 2021-03-17 | 2026-11-18 | 2073 | 0 | ok |
| SOL | Stablecoin supply | DefiLlama | 2021-09-10 | 2026-11-18 | 1653 | 243 | ok; gap preserved |
| BNB | Market cap | Coin Metrics Community | 2017-07-15 | 2019-04-22 | 647 | 0 | stale |
| BNB | Active addresses, transactions | Coin Metrics Community | 2017-07-05 | 2019-04-22 | 657 each | 0 | stale |
| BNB | TVL | DefiLlama | 2020-10-30 | 2026-11-18 | 2211 | 0 | ok |
| BNB | Stablecoin supply | DefiLlama | 2020-08-29 | 2026-11-18 | 2222 | 51 | ok; gap preserved |

DefiLlama stablecoin supply has two known multi-day gaps: SOL
2021-09-11 through 2022-05-11 (243 days), and BNB 2020-08-30 through
2020-10-19 (51 days). BTC hashrate and fees each have three missing days in
their stored ranges; these remain gaps. BTC hashrate on 2026-11-18 was
approximately `1.0522e21 H/s`; ETH TVL on 2021-11-09 was `$107.424B`.

The ingested Coin Metrics BNB series shown above stops at 2019-04-22 and is
discontinued despite historical points; the rows are scheduled for explicit
purge in the follow-up ingestion correction. SOL's requested Coin Metrics
metrics returned HTTP 403 and are stored as unavailable. Coin Metrics
Community data is non-commercial and requires attribution.
