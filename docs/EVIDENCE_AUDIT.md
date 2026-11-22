# Evidence Layer Feasibility Audit

**Audit date:** 2026-11-22

This report is a feasibility snapshot, not legal advice. Terms can change.
Results depend on VPN, IP address, network date, and provider reachability.
No product code, migration, dependency, test, or configuration was changed.

## Method

Requests used `ChainCompass-audit/1.0 (research project)`, at most one GET per
distinct URL, and a sleep of at least one second between requests to the same
host. The audit read [DATA_AUDIT.md](DATA_AUDIT.md) first and did not repeat
its existing data-source findings. It did not fetch article pages or store
full article text in the repository.

**Verification limitation:** the feed script fetched robots.txt for the news
hosts but did not actually evaluate `can_fetch` for the feed paths before
requesting those feeds. The probability and on-chain scripts also did not
fetch robots.txt for their hosts before requests. Therefore, this run did not
meet the robots pre-check requirement, and no source can be called permitted
for automated use based on this audit. RSS/API reachability below is only a
record of the returned HTTP responses, not permission to automate access.
The Coin Metrics requests used an incorrect catalog path
(`/v4/catalog-all/assets/{asset}/metrics`); its 404 responses do not establish
catalog availability or absence of metrics. Do not treat Part C as a completed
Coin Metrics catalog audit.

Third-party request count: 33 total calls (29 bounded feed/API GET requests:
18 news feed/robots checks, 3 probability-source checks, and 8 on-chain checks;
plus 4 configured-provider calls for the smoke test).

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

| Source | Feed URL candidate / check method | robots.txt HTTP | Feed HTTP | Type | Items | Newest age | Update spread | Fields | Summary | Reachability | Reuse / ToS | Data label |
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
so reuse, republication, and AI-processing terms remain UNVERIFIED. The
robots HTTP result is not a path-specific permission result. No Persian public
crypto/news feed was confirmed.

### News audit label count

AVAILABLE 6; NOT AVAILABLE FREE 2; UNVERIFIED 1; DISALLOWED 0. Permission
status for every candidate remains UNVERIFIED.

## Part B — Source-attributed probabilities

| Source | Documented / key-less check | Redisplay or ToS | Rate-decision market observed | Volume/liquidity fields | Country restrictions | Label |
|---|---|---|---|---|---|---|
| Polymarket Gamma API | Candidate endpoint returned HTTP 406; docs not verified | UNVERIFIED | no usable market payload returned | none returned | terms/geo restrictions not established | UNVERIFIED |
| Kalshi public market API | HTTP 200 JSON; candidate endpoint | UNVERIFIED | no Fed/FOMC/rate match in the sampled 100 open markets | match-specific fields not returned; schema not reviewed for this audit | not established by response | UNVERIFIED |
| CME FedWatch | HTTP 200 HTML tool page; no API endpoint checked | UNVERIFIED | web page reachable, no market data extracted | no API volume/liquidity fields verified | UNVERIFIED | UNVERIFIED |
| Central-bank expectation surveys | not queried | UNVERIFIED | no source endpoint verified | — | — | UNVERIFIED |

The Polymarket 406 did not yield a market payload. Kalshi returned an open-market
payload, but the bounded 100-item filter did not expose a rate-decision match
and the redisplay terms were not verified.

### Probability audit label count

AVAILABLE 0; NOT AVAILABLE FREE 0; UNVERIFIED 4.

## Part C — On-chain behavior data

The attempted Coin Metrics catalog URLs for `btc`, `eth`, `sol`, and `bnb_bsc`
used an incorrect route and returned HTTP 404. No actual metric IDs or sample
data requests were confirmed; these responses are not evidence of metric
absence. Existing [DATA_AUDIT.md](DATA_AUDIT.md) evidence remains
separate: BTC/ETH active addresses and transaction counts were measured in
Community API probes, while SOL and BNB Chain holders/flows were unavailable or
discontinued in that prior audit.

| Source / check | HTTP | Freshness / history | Candidate behavior fields | Result | Label |
|---|---:|---|---|---|---|
| Coin Metrics `btc` catalog | 404 | UNVERIFIED | none established | incorrect candidate route; catalog not audited | UNVERIFIED |
| Coin Metrics `eth` catalog | 404 | UNVERIFIED | none established | incorrect candidate route; catalog not audited | UNVERIFIED |
| Coin Metrics `sol` catalog | 404 | UNVERIFIED | none established | incorrect candidate route; catalog not audited | UNVERIFIED |
| Coin Metrics `bnb_bsc` catalog | 404 | UNVERIFIED | none established | incorrect candidate route; catalog not audited | UNVERIFIED |
| DefiLlama CEX endpoint | 200 | payload received | only top-level keys recorded; detailed fields not inspected | behavior indicator not established | UNVERIFIED |
| Blockchair BTC stats | 200 | payload received | only top-level keys recorded; detailed fields not inspected | behavior indicator not established | UNVERIFIED |
| Blockchain.info BTC transaction chart | 200 | chart payload received; values not summarized | transaction chart endpoint; freshness/history not verified | behavior indicator not established in this audit | UNVERIFIED |
| mempool.space BTC hashrate | 200 | payload received; values not summarized | hashrate endpoint; freshness/history not verified | behavior indicator not established in this audit | UNVERIFIED |

Per-chain result:

| Chain | Descriptive indicators | Evidence status |
|---|---|---|
| BTC | Prior audit has address/activity and network series; no 11C holder-distribution, large-holder, or exchange-flow metric was verified | UNVERIFIED |
| ETH | Prior audit has address/activity data; no 11C holder-distribution, large-holder, or exchange-flow metric was verified | UNVERIFIED |
| SOL | No 11C holder-distribution, exchange-inflow/outflow, or large-holder metric verified | UNVERIFIED |
| BNB Chain | No 11C holder-distribution, exchange-inflow/outflow, or large-holder metric verified; prior legacy BNB series do not establish BNB Chain coverage | UNVERIFIED |

### On-chain audit label count

AVAILABLE 0; NOT AVAILABLE FREE 0; UNVERIFIED 8; DISCONTINUED 0.
Existing `DATA_AUDIT.md` findings are prior evidence, not fresh 11C measurements.

## Part D — LLM extraction smoke

This was a 12-item smoke test, not an evaluation. The same two batches of six
real feed items were sent twice, using the unchanged prompt, for four provider
calls total. Strict JSON was requested but the existing app did not send a
provider `response_format` or JSON structured-output mode.

| Measure | Result |
|---|---|
| JSON validity | 4/4 batch responses valid JSON (100%) |
| Enum validity | 24/24 records valid (100%) |
| Attributed probabilities | 0 non-null probability objects in the retained repeat responses; no attribution to verify there. First-run outputs were not retained, so manual review does not cover that run. |
| Latency | First run: 9,857 ms and 865 ms; repeat: 2,447 ms and 1,103 ms |
| Structured-output mode | NOT APP-ENABLED; prompt-only JSON |
| Non-English/Persian | NOT TESTED; no Persian feed was found |

The smoke script reported the provider configured as `openai_compatible`, host `openrouter.ai`,
model `google/gemini-2.5-flash-lite`, and key state `set`. No key value was
printed or stored.

## Recommended shortlist for 11D

No source is approved for collection from this audit. The following six were
reachable candidates for a later permission-and-terms review only:

1. CoinDesk RSS — reachable, 3.95-hour newest item, short summaries.
2. Cointelegraph RSS — reachable, 3.46-hour newest item, longer summaries.
3. Decrypt RSS — reachable, 3.94-hour newest item, short summaries.
4. The Block RSS — reachable, 20.67-hour newest item.
5. Federal Reserve press RSS — reachable, 44.71-hour newest item.
6. SEC press RSS — reachable, 47.91-hour newest item.

No feed, probability, or on-chain source is cleared for an 11D build by this
run because robots path permissions and reuse terms were not verified.
Recommended shortlist for implementation: **none**. The six reachable feeds
above are only candidates for a properly permission-checked follow-up. Kalshi
lacked a verified rate match; the Coin Metrics catalog was not audited through
a valid path. Existing DATA_AUDIT.md BTC history may be considered separately
after an explicit terms review.

## NOT BUILDING (and why)

- Automated news-feed ingestion: robots path permissions and reuse terms were
  not verified.
- Bitcoin Magazine and BIS feed ingestion: no usable RSS response was
  observed at the tested candidate URLs.
- ECB feed ingestion: response could not be established.
- Live macro probability display: no source was confirmed with both a
  verified rate market and redisplay terms.
- Kalshi probability display: sampled open-market output lacked a verified
  rate-decision match and redistribution terms remain unconfirmed.
- Holder-distribution and exchange-flow ingestion: Coin Metrics catalog paths
  were incorrect and no other endpoint was inspected deeply enough to confirm
  a current metric.
- Public Dune or Flipside ingestion: account-gated sources are excluded.
- Full-article scraping or republication: the audit used feed metadata only,
  and reuse terms remain unverified.
- Persian extraction workflow: no confirmed public Persian crypto/news feed.

## Limits

This is a technical and terms-reuse feasibility report, not legal advice.
robots.txt and terms pages can change; results are observations for this
machine, date, and network path. This run did not correctly enforce its
robots pre-check requirement; do not use it as clearance for automated
collection. No claim is made that unavailable or missing pages are absent from
all regions or forever. No market number or model result is described as
definitive.
