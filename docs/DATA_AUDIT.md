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

The historical TVL ranges measured in the live run start in 2017-09-27 for
ETH, 2021-03-17 for SOL, and 2020-10-30 for BNB. The global stablecoin chart
has 3278 points from 2017-11-29 to 2026-11-19 with no missing days.

## Source license and terms

| Source | Terms link | Attribution or legal status |
|---|---|---|
| DefiLlama | https://defillama.com/terms | UNVERIFIED; preserve attribution and review terms |
| CoinGecko | https://www.coingecko.com/en/api_terms | Attribution required by its free API terms |
| Coin Metrics | https://coinmetrics.io/terms/ | UNVERIFIED; community terms apply |
| mempool.space | https://mempool.space/docs/api/rest | UNVERIFIED; rate-limit/attribution terms must be reviewed |
| Blockchain.info | https://www.blockchain.com/legal/privacy | UNVERIFIED; chart/API terms require review |
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
- **Primary BNB active addresses and tx count:** Coin Metrics community
  `AdrActCnt` and `TxCnt`, both 200. Market cap and price 200. Fees/hashrate
  are explicit 400; hashrate is also NOT APPLICABLE for PoS.
- **Primary ETH/SOL/BNB TVL and stablecoin supply:** DefiLlama.
- **Primary BTC hashrate:** mempool hashrate; Blockchain.info fallback.
- **Primary BTC fees:** mempool recommended fees plus successful
  Blockchain.info `transaction-fees` variant.

## Network Health Score candidate components

| Component | BTC | ETH | SOL | BNB | Source | History depth | Status |
|---|---|---|---|---|---|---|---|
| Price | AVAILABLE | AVAILABLE | AVAILABLE via Binance | AVAILABLE via Binance | Binance klines | BTC/ETH/SOL/BNB earliest candles 2017-2020 | computable now |
| Volume | AVAILABLE | AVAILABLE | AVAILABLE via Binance | AVAILABLE via Binance | Binance klines | BTC/ETH/SOL/BNB earliest candles 2017-2020 | computable now |
| Market cap | AVAILABLE | AVAILABLE | UNVERIFIED / CoinGecko stopped | UNVERIFIED / CoinGecko stopped | CoinGecko, Coin Metrics | BTC/ETH 365d plus Coin Metrics 1y probe window | needs more research |
| Active addresses | AVAILABLE | AVAILABLE | UNVERIFIED | AVAILABLE | Coin Metrics Community | 2025-11-20 to 2026-11-19 probe window | needs more research |
| Tx count | AVAILABLE | AVAILABLE | UNVERIFIED | AVAILABLE | Coin Metrics Community | 2025-11-20 to 2026-11-19 probe window | needs more research |
| Fees | AVAILABLE | UNVERIFIED | UNVERIFIED | UNVERIFIED | mempool/Blockchain/Coin Metrics | BTC current and 30d variants | needs more research |
| TVL | UNVERIFIED (BTC 404) | AVAILABLE | AVAILABLE | AVAILABLE | DefiLlama | years of measured chain history | computable now |
| Stablecoin supply | UNVERIFIED (BTC 404) | AVAILABLE | AVAILABLE with 243 gaps | AVAILABLE with 51 gaps | DefiLlama | years of measured series | computable now |
| Hashrate | AVAILABLE | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | mempool/Blockchain | BTC 365d or 1y | computable now |
| Validators | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED until dedicated free source | none measured | needs more research |

Missing components remain unavailable and must not be imputed.
