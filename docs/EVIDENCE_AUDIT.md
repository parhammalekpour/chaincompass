# Evidence Layer Feasibility Audit

**Audit date:** 2026-11-22

This report is a feasibility snapshot, not legal advice. Terms can change.
Results depend on VPN, IP address, network date, and provider reachability.
No product code, migration, dependency, test, or configuration was changed.

## Method

Requests used `ChainCompass-audit/1.0 (research project)`, at most one GET per
distinct URL, and a sleep of at least one second between requests to the same
host. The audit read [DATA_AUDIT.md](DATA_AUDIT.md) first and did not repeat
its existing data-source findings. It fetched RSS/XML feeds and documented
read-only API endpoints only. It did not fetch article pages or store full
article text in the repository.

Third-party request count: 29 bounded HTTP requests (18 feed/robots checks,
3 probability-source checks, 12 on-chain checks), plus 2 configured-provider
calls for the smoke test. Provider calls are reported separately from
third-party audit requests.

## Labels

- **AVAILABLE:** observed response was usable and fresh enough for the stated
  descriptive purpose.
- **NOT AVAILABLE FREE:** a free, key-less result was not observed or was stale,
  empty, blocked, absent, or account-gated.
- **NOT APPLICABLE:** the metric type does not apply to the chain.
- **UNVERIFIED:** access or data semantics could not be established.
- **DISCONTINUED:** existing evidence shows the series ended or no longer
  represents the requested chain.
- **DISALLOWED:** robots or terms explicitly forbid automated access.

No DISALLOWED source was identified. Some robots.txt and terms results remain
UNVERIFIED because the public page or explicit feed-path rule could not be
established without exceeding the bounded audit scope.

## Part A — News feeds

The crypto and institutional feeds below were checked for `/robots.txt` and
the candidate RSS URL. `The Block` and the institutional feeds have different
dates and update cadence; intervals are a spread of the newest ten items.

| Source | Feed URL found / check method | robots | HTTP | Type | Items | Newest age | Update spread | Fields | Summary | Reachability | Reuse / ToS | Label |
|---|---|---|---:|---|---:|---:|---|---|---|---|---|---|
| CoinDesk | Memory candidate `/arc/outboundfeeds/rss/` | 200 | 200 | application/xml | 25 | 3.95 h | ~0.29–20.17 h | title, summary, link, date | short | reachable | UNVERIFIED | AVAILABLE |
| Cointelegraph | Memory candidate `/rss` | 200 | 200 | XML UTF-8 | 30 | 3.46 h | ~1.0–19.66 h | title, summary, link, date | long | reachable | UNVERIFIED | AVAILABLE |
| Decrypt | Memory candidate `/feed` | 200 | 200 | application/xml | 37 | 3.94 h | ~0.50–20 h | title, summary, link, date | short | reachable | UNVERIFIED | AVAILABLE |
| Bitcoin Magazine | Memory candidate `/.rss/full` | 200 | 200 | text/html | 0 | — | — | none | none | reachable, not RSS | UNVERIFIED | NOT AVAILABLE FREE |
| The Block | Memory candidate `/rss.xml` | 200 | 200 | text/xml UTF-8 | 20 | 20.67 h | ~0.08–10.90 h | title, summary, link, date | short | reachable | UNVERIFIED | AVAILABLE |
| Federal Reserve | Memory candidate `/feeds/press_all.xml` | 404 | 200 | text/xml | 20 | 44.71 h | ~0.75–117.75 h | title, summary, link, date | short | reachable | UNVERIFIED | AVAILABLE |
| SEC | Memory candidate `/rss/news/press.xml` | 200 | 200 | application/rss+xml UTF-8 | 25 | 47.91 h | ~3.58–146.54 h | title, summary, link, date | long | reachable | UNVERIFIED | AVAILABLE |
| ECB | Memory candidate `/rss/press.html` | no response | error | — | 0 | — | — | — | — | no usable response | UNVERIFIED | UNVERIFIED |
| BIS | Memory candidate `/doclist/press_releases.rss` | 200 | 404 HTML | text/html | 0 | — | — | none | none | reachable, feed missing | UNVERIFIED | NOT AVAILABLE FREE |

The homepages and candidate feeds were used as memory candidates; the
Bitcoin Magazine candidate returned HTML, the BIS candidate returned HTML/404,
and ECB produced no usable response. This is not evidence of a source's
complete lack of syndication. Candidate ToS/reuse pages were not confirmed,
so reuse, republication, and AI-processing terms remain UNVERIFIED. No Persian
public crypto/news feed was confirmed.

### News audit label count

AVAILABLE 5; NOT AVAILABLE FREE 2; UNVERIFIED 1; DISALLOWED 0.

## Part B — Source-attributed probabilities

| Source | Documented / key-less check | Redisplay or ToS | Rate-decision market observed | Volume/liquidity fields | Country restrictions | Label |
|---|---|---|---|---|---|---|
| Polymarket Gamma API | Public endpoint returned HTTP 406; documentation status UNVERIFIED | UNVERIFIED | no usable market payload returned | none returned | terms/geo restrictions not established | NOT AVAILABLE FREE |
| Kalshi public market API | HTTP 200 JSON, no key on returned public endpoint | UNVERIFIED | no Fed/FOMC/rate match in 100 open markets returned | volume/open-interest fields can exist in returned schema | no country restriction stated in response | UNVERIFIED |
| CME FedWatch | HTTP 200 HTML tool page; no free documented key-less API established | UNVERIFIED | web tool HTML was reachable | no API volume/liquidity fields verified | UNVERIFIED | NOT AVAILABLE FREE |
| Central-bank expectation surveys | not queried | UNVERIFIED | no source endpoint verified | — | — | UNVERIFIED |

The Polymarket 406 did not yield a market payload. Kalshi returned an open-market
payload, but the bounded 100-item filter did not expose a rate-decision match
and the redisplay terms were not verified.

### Probability audit label count

AVAILABLE 0; NOT AVAILABLE FREE 2; UNVERIFIED 2.

## Part C — On-chain behavior data

The Coin Metrics catalog URLs for `btc`, `eth`, `sol`, and `bnb_bsc` returned
HTTP 404, so no actual metric IDs or sample data requests could be confirmed
from those routes. Existing [DATA_AUDIT.md](DATA_AUDIT.md) evidence remains
separate: BTC/ETH active addresses and transaction counts were measured in
Community API probes, while SOL and BNB Chain holders/flows were unavailable or
discontinued in that prior audit.

| Source / check | HTTP | Freshness / history | Candidate behavior fields | Result | Label |
|---|---:|---|---|---|---|
| Coin Metrics `btc` catalog | 404 | UNVERIFIED | no candidate metric list returned | catalog route did not resolve | UNVERIFIED |
| Coin Metrics `eth` catalog | 404 | UNVERIFIED | no candidate metric list returned | catalog route did not resolve | UNVERIFIED |
| Coin Metrics `sol` catalog | 404 | UNVERIFIED | no candidate metric list returned | catalog route did not resolve | UNVERIFIED |
| Coin Metrics `bnb_bsc` catalog | 404 | UNVERIFIED | no candidate metric list returned | catalog route did not resolve | UNVERIFIED |
| DefiLlama CEX endpoint | 200 | payload received | top-level CEX and CoinGecko-volume aggregates; detailed balance history not inspected | not established as a holder-distribution source | UNVERIFIED |
| Blockchair BTC stats | 200 | payload received | context/data keys; balance-distribution or exchange-flow fields not established | general BTC stats only | UNVERIFIED |
| Blockchain.info BTC transaction chart | 200 | 30-day chart requested | transaction-count time series | descriptive chain activity, not holder identity or exchange flow | UNVERIFIED |
| mempool.space BTC hashrate | 200 | one-week hash-rate request | network difficulty/hash-rate fields | descriptive network security/activity, not holder movement | AVAILABLE — as hashrate only |

Per-chain result:

| Chain | Descriptive indicators | Evidence status |
|---|---|---|
| BTC | BTC hashrate, transaction-count chart, and existing Coin Metrics address/activity data | Hashrate and prior measured BTC address/activity evidence exist; 11C holder/exchange-flow catalog was UNVERIFIED |
| ETH | Existing Data Audit address/activity evidence; no 11C holder-distribution or exchange-flow source confirmed | NOT AVAILABLE FREE for 11C holder/exchange-flow indicators |
| SOL | No confirmed holder-distribution, exchange-inflow/outflow, or large-holder metric | NOT AVAILABLE FREE |
| BNB Chain | No confirmed BNB Chain holder-distribution, exchange-inflow/outflow, or large-holder metric | NOT AVAILABLE FREE / legacy BNB data DISCONTINUED |

### On-chain audit label count

AVAILABLE 1 (hashrate only); NOT AVAILABLE FREE 0; UNVERIFIED 7; DISCONTINUED 1.

## Part D — LLM extraction smoke

This was a 12-item smoke test, not an evaluation. Two batches of six real feed
items were sent. Strict JSON was requested but the existing app did not send a
provider `response_format` or JSON structured-output mode.

| Measure | Result |
|---|---|
| JSON validity | 2/2 batch responses valid JSON (100%) |
| Enum validity | 12/12 records valid (100%) |
| Invented attributed probabilities | 0 |
| Latency | 9,857 ms and 865 ms |
| Structured-output mode | NOT APP-ENABLED; prompt-only JSON |
| Non-English/Persian | NOT TESTED; no Persian feed was found |

The provider was configured as `openai_compatible`, host `openrouter.ai`,
model `google/gemini-2.5-flash-lite`, and key state `set`. No key value was
printed or stored.

## Recommended shortlist for 11D

At most six items, ranked only for feasibility:

1. CoinDesk RSS — reachable, 3.95-hour newest item, short summaries.
2. Cointelegraph RSS — reachable, 3.46-hour newest item, longer summaries.
3. Decrypt RSS — reachable, 3.94-hour newest item, short summaries.
4. The Block RSS — reachable, 20.67-hour newest item.
5. Federal Reserve press RSS — reachable, 44.71-hour newest item.
6. SEC press RSS — reachable, 47.91-hour newest item.

No probability or on-chain source is a clear 11D build recommendation in this
run. Polymarket and CME were blocked or not API-established; Kalshi lacked a
verified rate match and redisplay terms; Coin Metrics routes remained 404.
Existing BTC hashrate and transaction series may be useful as documented
descriptive chain indicators, subject to a separate terms/dependency review.

## NOT BUILDING (and why)

- News extraction from Bitcoin Magazine and BIS: no usable RSS response was
  observed.
- ECB feed ingestion: response could not be established.
- Live price or macro probability extraction: no key-less, documented,
  redisplay-cleared source produced a verified rate-decision market.
- Kalshi probability display: open-market output lacked a verified
  rate-decision match and redistribution terms remain unconfirmed.
- Holder-distribution and exchange-flow ingestion: no matching confirmed
  free, key-less, current source was measured for the four chains.
- Public Dune or Flipside ingestion: account-gated sources are excluded.
- Full-article scraping or republication: the audit used feed metadata only,
  and reuse terms remain unverified.
- Persian extraction workflow: no confirmed public Persian crypto/news feed.

## Limits

This is a technical and terms-reuse feasibility report, not legal advice.
robots.txt and terms pages can change; results are observations for this
machine, date, and network path. No claim is made that unavailable or missing
pages are absent from all regions or forever. No market number or model result
is described as definitive.
