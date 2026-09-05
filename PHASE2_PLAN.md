# Vercel Phase 2 — MACRO tab build plan

Status: **plan only, no code yet**. Builds on the architecture findings in
`overnight-report-20260905.md` Task 2. Approved decisions from Claude.ai
review (2026-09-05):

1. ~~Render paid tier~~ **SUPERSEDED (2026-09-05, second review): caching
   decision is S3-as-cache, not local disk or Upstash.** Variants A and B
   below are kept for the record but are no longer the plan — see
   **Variant C: S3-as-cache** for the actual chosen architecture. This
   also means the Render-paid-tier dependency is gone: Variant C works
   identically on free or paid tier, since the cache lives outside the
   Render instance entirely (same reasoning that made Variant B
   attractive, but with zero new services rather than adding Upstash).
2. Sub-endpoint architecture (3 endpoints grouped by cache lifetime) — approved.
3. Plotly.js/react-plotly.js — approved.
4. GDP component contributions panel — confirmed dead code, excluded from scope.
5. **DECIDED (2026-09-05, canary review): API endpoints return raw data,
   not `fig.to_dict()`.** The `/api/macro/rates` canary built and
   verified this way — frontend components build Plotly.js figures from
   raw series/scalars client-side, rather than the backend pre-building
   Plotly figure objects and shipping those. **This is now the standing
   pattern for all Vercel phases going forward, not just Phase 2** —
   supersedes the "cache the finished computed response payload...
   including `fig.to_dict()` where applicable" language in Variant C
   below, which is left as historical context rather than edited in
   place. Cache payloads store raw data, same as the API response shape.

## Recap: what's being built (see overnight report for full detail)

9 chart panels across 3 endpoints, all backed by live FRED/BEA/BLS +
yfinance calls (not the S3 workbook — that's Phase 1's LIVE tab only):

- `/api/macro/rates` — Fed Funds Range, FOMC probabilities + meeting
  table, Yield Curve, Spreads, Lending Standards
- `/api/macro/growth` — GDP (3 sub-charts), Inflation, Core PCE
- `/api/macro/dot-plot` — SEP dot plot (static CSV, near-never changes)

Charting: Plotly.js via `react-plotly.js`, backend returns `fig.to_dict()`
from ported `go.Figure` construction code, frontend renders near-verbatim.

---

## Variant A (primary, pending payment decision): Render paid tier

**Assumption**: Render's paid web service tier ($7/mo, "Starter" or
equivalent) — no spin-down, persistent local disk across requests within
the instance's lifetime (still ephemeral across actual redeploys, but
stable for the caching window sizes in use here: 12h–168h).

### Architecture
Port Streamlit's caching pattern from `data_cache.py`/`macro_data.py`
nearly as-is:
- Local parquet cache files under a `cache/` directory in the Render
  service, same staleness-window logic (`is_stale(path, max_age_hours)`).
- Each of the 3 endpoints checks its panels' cache files first; on a
  miss/stale, fetches fresh from FRED/BEA/BLS/yfinance and rewrites the
  cache file, exactly mirroring `load_price`/`load_model`'s
  check-then-fetch-then-write pattern from Phase 1's dependency (`data_cache.py`).
- No new AWS infrastructure needed — this variant needs zero new moving
  parts beyond Phase 1's existing setup, which is its main appeal.

### Build steps
1. Confirm Render tier upgrade has actually happened (blocker — do not
   start until payment is confirmed, since Variant A's entire design
   depends on the persistent-disk assumption holding).
2. Port `macro_data.py`/`fomc_data.py` fetch functions into the API
   service (new `api/macro_data.py`, mirroring Phase 1's
   `api/dashboard_data.py` module pattern) — reuse `requests`-based FRED/BEA/BLS
   calls verbatim, add `yfinance`/`beautifulsoup4`/`pandas` to
   `requirements.txt` (see Dependencies in overnight report).
3. Add local file-cache helper (`api/cache.py`, porting `is_stale`/`cache_path`
   from `data_cache.py`) — same staleness windows as Streamlit (12h
   default, 24h Fed Funds, 168h Lending Standards).
4. Build the 3 endpoints, each assembling its panels' data + calling the
   ported `go.Figure` builders, returning `fig.to_dict()` per chart plus
   any scalar/table data (e.g. FOMC meeting table rows, GDP metric stats).
5. Add `FRED_API_KEY`/`BEA_API_KEY`/`BLS_API_KEY` as new Render env vars
   (same `sync: false` pattern as `API_TOKEN`/AWS credentials).
6. Frontend: `plotly.js` + `react-plotly.js` added to `web/package.json`,
   build the 6 new components identified in the overnight report
   (`LineChart`, `BarChart`, `DotPlotChart`, `YieldCurvePanel`,
   `FomcProbabilityPanel`, `MetricStat`), 3 independent data-fetch
   sections (one per endpoint) so each can load/error independently —
   this is the explicit relaxation of Phase 1's "one page-level skeleton"
   principle flagged in the overnight report's risk #5, needed because
   panels here genuinely have different load times.
7. Local test, comparison against Streamlit MACRO tab panel-by-panel
   (same verification discipline as Phase 1).
8. Deploy, verify prod.

### Pros / cons vs. Variant B
- Pro: minimal new infrastructure, closest to a direct port, lowest
  build risk.
- Con: $7/mo recurring cost, and the cache still doesn't survive an
  actual redeploy (each code push clears local disk) — acceptable given
  redeploys are infrequent relative to the staleness windows, but worth
  knowing.

---

## Variant B (fallback): free tier + Upstash Redis

**Assumption**: stay on Render's free tier (accept cold-start spin-down),
use Upstash Redis's free tier (serverless Redis, REST + Redis protocol,
no persistent connection needed — works from a cold-starting stateless
function) as the cache layer instead of local disk.

### Why Upstash specifically
- Free tier is genuinely usable for this workload (low request volume,
  small payloads — cached JSON/dict blobs per panel, not raw parquet
  files) — Upstash's free tier limits are request-count and
  storage-size based, both comfortably within a low-traffic internal
  dashboard's needs.
- REST API means no persistent TCP connection management from a
  cold-starting Python process — a plain `requests`/`httpx` call per
  cache read/write, which fits Render free tier's spin-up/spin-down
  lifecycle far better than a stateful Redis client would.
- Survives redeploys (external to the Render instance entirely) —
  actually a strict improvement over Variant A's redeploy-clears-cache
  behavior, at the cost of one more external dependency.

### Architecture changes from Variant A
- Replace the local parquet-file cache (`api/cache.py`) with a small
  Upstash-backed cache module: same `is_stale`/`get`/`set` shape, but
  backed by Upstash's REST `GET`/`SET` with a TTL matching each panel's
  staleness window (Redis `EX` semantics map directly onto the existing
  12h/24h/168h windows — arguably simpler than reimplementing file-mtime
  staleness checks).
- Cached values stored as serialized JSON (the panel's final response
  payload, e.g. `fig.to_dict()` + scalar stats) rather than raw parquet
  — this is a reasonable simplification since Phase 2 doesn't need
  DataFrame roundtripping the way Streamlit's cache does (Streamlit
  caches raw fetched data and recomputes figures every render; here, once
  a panel's full response is computed, caching the finished response is
  both simpler and sufficient).
- New env vars: `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`
  (from Upstash's dashboard, same "set directly in Render, never share
  with Claude" pattern established for AWS/API_TOKEN this session).
- New dependency: `upstash-redis` (official Python SDK) or a plain
  `requests` wrapper against Upstash's REST API — the latter avoids an
  extra dependency for what's really just two HTTP calls (GET/SET),
  worth deciding at build time based on how much the SDK actually buys
  over hand-rolling it.

### Build steps
Same as Variant A steps 2, 4-8, with step 3 replaced by the Upstash
cache module instead of the local-file one, and no dependency on a
Render tier upgrade — can start immediately once approved.

### Pros / cons vs. Variant A
- Pro: no recurring Render cost, cache actually survives redeploys
  (better than Variant A here), can start building today.
- Con: one more external service/account to manage (Upstash), cold-start
  latency on Render free tier still applies to the *first* request after
  spin-down even with a warm cache (the ~45s cold start observed for
  Phase 1 is a Render platform behavior, not a caching problem — Variant
  B doesn't fix that, only Variant A's paid tier does), so free-tier
  users still see one slow request per idle period regardless of caching
  strategy.

---

## Variant C (DECIDED — this is the plan): S3-as-cache

**Assumption**: none beyond what Phase 1 already has. Reuses the existing
`cmon-stage-backend-369568916817-ap-southeast-1-reports` S3 bucket and the
existing `cgi-vercel-render-svc` IAM user, extended with one new
permission (below). Zero new services, zero new accounts, works
identically on Render's free or paid tier since the cache lives outside
the Render instance entirely.

### Why this over A and B
- Same redeploy-survival property as Variant B (external to the Render
  instance), without adding a new vendor/account (Upstash) to manage.
- Reuses infrastructure and IAM patterns already proven in Phase 1 —
  the team already knows how to read/write this bucket, monitor it, and
  reason about its permissions. Net new operational surface area is one
  IAM policy statement, not a new service.
- Removes the Render-paid-tier dependency entirely — the caching
  architecture question and the "should we pay for Render" question are
  now fully decoupled, which was Variant A's main drawback.

### Cache key structure
One S3 object per cache key (not date-partitioned) — mirrors Streamlit's
existing `cache_path(kind, name)` → one file per kind/name pair, which
already encodes the right granularity (e.g. `model_compass_US.parquet`,
`macro_fed_funds_range.parquet`). Date-partitioned keys (e.g.
`Cache/2026-09-05/fed_funds.json`) were considered and rejected: several
panels cache multi-year time series (the 20-year yield history, GDPNow
timeline), so "today's partition" doesn't map cleanly onto what's being
cached, and date-partitioning would accumulate objects forever with no
natural expiry.

Proposed prefix and key pattern:
```
Cache/macro/{cache_key}.json
```
e.g. `Cache/macro/fed_funds_range.json`, `Cache/macro/effr.json`,
`Cache/macro/treasury_curve.json`, `Cache/macro/lending_standards.json`,
`Cache/macro/gdp.json`, `Cache/macro/gdp_nowcast.json`,
`Cache/macro/inflation.json`, `Cache/macro/pce.json` — one key per
distinct `macro_data.py`/`fomc_data.py` fetch function, same granularity
Streamlit's own cache files already use.

Each object stores the **finished, computed response payload** for that
panel (scalar stats + `fig.to_dict()` where applicable) as JSON — not
raw fetched series. Same reasoning as Variant B: Phase 2 doesn't need
DataFrame roundtripping the way Streamlit's render-every-time model does;
caching the finished response is simpler and sufficient, and avoids
needing `pyarrow`/parquet support on the API side at all.

### Cache invalidation strategy
On each request for a given cache key: `head_object` to read
`LastModified` (cheap — no body transfer), compare `now - LastModified`
against that key's TTL. If fresh, `get_object` and return the cached
payload directly. If stale or missing (`NoSuchKey`), fetch live from
FRED/BEA/BLS/yfinance, compute the response, `put_object` to refresh the
cache, then return it.

**TTL revision (2026-09-05 addendum)**: the initial draft mirrored
Streamlit's coarse 12h/24h/168h buckets. Per your confirmation that MACRO
data actually updates roughly every few days, and your explicit
per-source guidance, TTLs are now set **per cache key**, aligned to each
source's real publication cadence rather than Streamlit's original
groupings. Bias is toward longer TTLs — cadence match matters more than
staleness fear, and S3 `head_object`/`get_object` calls are free at this
volume regardless of TTL choice:

| Cache key | Source | Actual cadence | TTL | Rationale |
|---|---|---|---|---|
| `fed_funds_range` | FRED DFEDTARU/DFEDTARL | Daily (rarely changes) | **12h** | Your explicit "FRED Fed Funds: 12h" |
| `effr` / FOMC probabilities | FRED DFF + **yfinance** ZQ futures | Daily, but futures pricing moves intraday | **6h** | Your explicit "any yfinance-based fetch: 6h (rate-limit safety margin)" — this panel is yfinance-dependent |
| `fomc_meeting_calendar` | scraped (BeautifulSoup) | Changes only a few times/year | **7d** | Not in your explicit list; treated like the dot plot — meeting dates are near-static, matches your "err longer" guidance |
| `treasury_curve` | FRED DGS series | Daily | **6h** | Your explicit "Yield curve: 6h — relatively fresh matters more" |
| `spreads` | FRED T10Y2Y + HY OAS | Daily | **12h** | Not explicitly listed; same cadence class as Fed Funds, no "freshness matters more" flag like yield curve got, so defaulted to the daily-FRED bucket |
| `lending_standards` | FRED DRTSCILM (SLOOS) | Quarterly | **48h** | Not explicitly listed; grouped with GDP's quarterly cadence rather than Streamlit's old 168h — still generous relative to a quarterly release |
| `gdp` (BEA NIPA quarterly print + ALFRED vintages) | BEA/ALFRED | Quarterly | **48h** | Your explicit "GDP (quarterly with vintages): 48h" |
| `gdp_nowcast` (Atlanta Fed GDPNow only) | FRED GDPNOW | Updates ~weekly within a quarter | **24h** | **DECIDED (2026-09-05, second addendum): split from `gdp` into its own cache key.** Rationale: the nowcast signal degrades meaningfully if served at 48h staleness given how much it moves within a quarter, unlike the quarterly print it was originally bundled with; splitting costs essentially nothing (one more S3 key, same `get`/`set` interface, no new code path) since the Streamlit panel already treats GDPNow as a visually distinct sub-chart from the BEA bars — this mirrors an existing UI distinction rather than inventing a new one |
| `inflation` (CPI/Core CPI/PPI) | BLS | Monthly | **24h** | Your explicit "CPI: 24h" |
| `pce` (Core PCE) | BEA | Monthly | **24h** | Not explicitly listed; same monthly cadence as CPI, matched to that bucket |
| SEP dot plot | static CSV | A few times/year, manual update | **7d** (or excluded from caching entirely) | Your explicit "Dot plot: 7d" — though as noted in the original plan, this is already a static file, not a live fetch, so a TTL here is almost academic; redeploy-on-update remains the simplest option and 7d is a reasonable belt-and-suspenders cap either way |

This is a straightforward per-key parameterization of `is_stale(path,
max_age_hours)` from `data_cache.py` — same function shape, just called
with a different `max_age_hours` per cache key instead of one shared
default, with `path.stat().st_mtime` replaced by an S3 `head_object`
call's `LastModified`.

### IAM policy update needed

**Current policy only grants `s3:GetObject` on `Dashboard/*` and
`s3:ListBucket` scoped to that same prefix — it cannot read OR write the
new `Cache/*` prefix at all.** Two changes needed: extend the list
condition to cover both prefixes, and add `s3:PutObject` (plus
`s3:GetObject`) scoped to `Cache/*`.

**Printed here for you to apply manually in the AWS console — I have not
touched IAM, per your instruction:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListDashboardAndCachePrefixes",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::cmon-stage-backend-369568916817-ap-southeast-1-reports",
      "Condition": {
        "StringLike": {
          "s3:prefix": ["Dashboard/*", "Cache/*"]
        }
      }
    },
    {
      "Sid": "ReadDashboardReports",
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::cmon-stage-backend-369568916817-ap-southeast-1-reports/Dashboard/*"
    },
    {
      "Sid": "ReadWriteMacroCache",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::cmon-stage-backend-369568916817-ap-southeast-1-reports/Cache/*"
    },
    {
      "Sid": "QueryModelHistoryFallback",
      "Effect": "Allow",
      "Action": "dynamodb:Query",
      "Resource": "arn:aws:dynamodb:ap-southeast-1:369568916817:table/cmon-stage-backend-model-history"
    }
  ]
}
```

Changes from the current live policy: `ListDashboardAndCachePrefixes`
replaces `ListDashboardPrefix` (now an array covering both prefixes
instead of just `Dashboard/*`), and `ReadWriteMacroCache` is new
(`ReadDashboardReports` and `QueryModelHistoryFallback` are unchanged
from what's already applied). This is still least-privilege: write
access is scoped narrowly to the cache prefix only, nothing else changes.

### Build steps
Same as Variant A's steps 2, 4-8, with step 3 replaced by an S3-backed
cache module (`api/cache.py`: `get(key) -> Optional[dict]` doing
`head_object`+TTL-check+`get_object`, `set(key, value)` doing
`put_object` with the JSON payload) — no new Python dependency, `boto3`
is already in `requirements.txt` from Phase 1. Add step 0: apply the
updated IAM policy above (your action, in console) before any live
testing against real S3 cache reads/writes can happen.

### Risk note carried over from Variant B
S3-as-cache does not fix Render free tier's cold-start latency any more
than Upstash did — a cold-starting request still pays the ~45s spin-up
cost observed in Phase 1 regardless of whether the cache itself responds
instantly once the process is running. If that latency is a real UX
concern, it's a Render-tier decision independent of this caching
architecture question, not something S3-as-cache resolves.

---

## Recommendation — DECIDED: Variant C (S3-as-cache)

Superseded the earlier "build against Variant A's structure, keep it
swappable" recommendation now that a decision has been made. Build
directly against Variant C's design: `api/cache.py` with the
`get(key)`/`set(key, value)` interface backed by S3 `head_object`/
`get_object`/`put_object`, per-key TTLs matching Streamlit's existing
windows. No Render tier decision blocks this anymore. Cold-start latency
on free tier remains a separate, real consideration (see Variant C's
risk note) — worth deciding independently, not a caching question.

## Unchanged from overnight report

Panel inventory, endpoint split, component sketch, charting library
choice, dependency list (beyond the cache-backend-specific ones above),
and risks #2-5 are all unchanged — see `overnight-report-20260905.md`
Task 2 for full detail, not repeated here.

**Still not started: no code written for Phase 2. This remains a planning
document pending your go-ahead to build.**
