# ChainCompass Free Data Audit

**Run date:** 2026-11-19

**Network condition:** Iran + VPN. Results may differ from a server abroad.

**Run duration:** 134.09 seconds. Requests were sequential, used
`ChainCompass-audit/0.1`, and used bounded history ranges.

## Reachability table

| Source | Probe | Reachable | Error class | HTTP | Latency |
|---|---|---|---|---:|---:|
| DefiLlama | Chain TVL list | Yes | none | 200 | 2000 ms |
| DefiLlama | Global stablecoin chart | Yes | none | 200 | 4841 ms |
| DefiLlama | ETH/SOL/BSC historical TVL | Yes | none | 200 | 1027-1901 ms |
| DefiLlama | ETH/SOL/BSC stablecoin supply | Yes | none | 200 | 5521-6984 ms |
| CoinGecko | Ping and current price/market cap/volume | Yes | none | 200 | 1023-2696 ms |
| CoinGecko | BTC/ETH 365-day charts | Yes | none | 200 | 819-1053 ms |
| CoinGecko | SOL 365-day chart | No | HTTP status; 429 | 429 | 1083 ms |
| CoinGecko | BNB chart | UNPROBED; source stopped at SOL 429 | none | - | - |
| Coin Metrics | Community catalog | Yes | none | 200 | 9176 ms |
| Coin Metrics | BTC/ETH/SOL/BNB community timeseries | No | HTTP status | 400 | 714-1172 ms |
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
| Active addresses | NOT AVAILABLE FREE: Coin Metrics 400 | NOT AVAILABLE FREE: Coin Metrics 400 | NOT AVAILABLE FREE: Coin Metrics 400 | NOT AVAILABLE FREE: Coin Metrics 400 |
| Tx count | NOT AVAILABLE FREE / UNVERIFIED; 30-day TPS chart is not count | NOT AVAILABLE FREE | NOT AVAILABLE FREE | NOT AVAILABLE FREE |
| Fees | mempool recommended fees current; chart 404 | NOT AVAILABLE FREE | NOT AVAILABLE FREE | NOT AVAILABLE FREE |
| TVL | NOT AVAILABLE FREE | DefiLlama 3341 points, 2026-11-19 staleness 16.68 h | DefiLlama 2074 points, 2026-11-19 staleness 16.68 h | DefiLlama 2212 points, 2026-11-19 staleness 16.68 h |
| Stablecoin supply | UNVERIFIED/NOT AVAILABLE by chain | DefiLlama 3278 points, no missing days | DefiLlama 1654 points, 243 missing days | DefiLlama 2223 points, 51 missing days |
| Hashrate/validators | mempool 1-year hashrate and Blockchain.info 365-day chart | UNVERIFIED | UNVERIFIED | UNVERIFIED |

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

**Primary source by metric**

- BTC/ETH/SOL/BNB price and volume: Binance public 365-day daily klines;
  CoinGecko as current market and fallback history source.
- ETH/SOL/BNB TVL: DefiLlama historical chain TVL.
- ETH/SOL/BNB/global stablecoin supply: DefiLlama stablecoin charts.
- BTC hashrate: mempool.space hashrate plus Blockchain.info fallback.
- ETH/SOL/BNB chain liveness: the corresponding public RPC endpoint.

**Fallbacks**

- CoinGecko current/simple-price endpoint is the market-cap/24h-volume fallback
  for all chains.
- Blockchair is a low-priority BTC/ETH network-stat fallback.
- Blockchain.info TPS and mempool recommended fees are BTC-context fallbacks,
  not substitutes for each chain's full transaction/fee dataset.

**ChainCompass will not offer**

- Coin Metrics active-address or transaction metrics for any chain under the
  tested community tier.
- ETH/SOL/BNB fee totals, because no audited source proved a free result.
- BTC TVL as a free network-TVL metric.
- ETH/SOL/BNB validator metrics without a later dedicated measurement.

**Network Health Score implications**

- BTC can honestly use measured price, volume, hashrate, public fee snapshot,
  RPC/block context, and TPS context where endpoints remain available.
- ETH can use measured market data, DefiLlama TVL/stablecoins, and RPC liveness.
- SOL can use measured market data, DefiLlama TVL/stablecoins, and RPC TPS
  sample coverage.
- BNB can use measured Binance/CoinGecko market data, DefiLlama TVL/stablecoins,
  and RPC block liveness.
- Missing components must remain unavailable, not imputed or averaged into a
  misleading health score.
