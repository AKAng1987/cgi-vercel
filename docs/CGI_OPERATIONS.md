# CGI — operations

What the system is, where every number comes from, what keeps it current,
and what to do when something looks wrong.

Written to be opened when something breaks. Verified against the live system
on 2026-09-27; where a fact was checked firsthand it says so, and where it is
an inference it says that too.

---

## 1. What CGI is

CGI (Compass Grid Identifier) reads the macro regime and says what it has
historically meant for a list of instruments. The regime is two 2×2 grids:
**Compass** = Liquidity × Credit, **Grid** = Growth × Inflation, giving 16
states C1–C4 × G1–G4. The current state is **C3G3**.

Each axis moves on one scheduled data release — FOMC sets Liquidity, SLOOS
sets Credit, CPI sets Inflation, GDP sets Growth. Those four are the
**state**. Everything else on the dashboard is **conditioning**: given the
state, what matters for the instrument in front of you.

CGI is an ideation tool. It does not place trades, hold positions, or know
about fills. Execution is a separate system that reads CGI through a
read-only interface.

---

## 2. Where the data comes from

Two questions per source: **is it stored, or fetched live?** A stored series
has a process maintaining it and a history we own. A live-fetched series has
neither — if the provider is down when the cache expires, there is nothing.

### Stored in AWS (DynamoDB `price-history`)

| What | Source | Maintained by | Cadence |
|---|---|---|---|
| ~146 equity/ETF prices | marketstack | `price-updater` | daily 00:05 UTC |
| ~50 macro series | FRED | `fred-data-updater` | daily 00:05 UTC |
| 7 Treasury tenors (`US01Y`…`US30Y`) | FRED | `us-yield-updater` | daily 00:05 UTC |
| GDP | FRED | `gdp-updater` | daily 00:05 UTC |
| 8 index/FX | Yahoo | `yahoo-finance-updater` | daily 00:10 UTC |
| inflation series | — | `inflation-rate-updater` | daily 00:15 UTC |
| derived metrics | computed | `derived-metrics-updater` | daily 00:20 UTC |
| BTC, ETH | coingecko | `crypto-price-updater` | daily 23:59 UTC |
| 15 FX pairs | alpha_vantage | `alpha-vantage-updater` | daily 02:15 UTC |
| 46 manual symbols | TradingView | **a Claude routine, not AWS** | monthly |

### Fetched live on every cache miss — NOT stored

| What | Source | Key needed | Feeds |
|---|---|---|---|
| Treasury curve, spreads, GDP, GDPNow, SLOOS | FRED | `FRED_API_KEY` | MACRO |
| CPI, core CPI, PPI | BLS | `BLS_API_KEY` | MACRO |
| Core PCE | BEA | `BEA_API_KEY` | MACRO |
| **Fed funds futures strip** | **yfinance** | none | **FOMC probabilities** |
| FOMC meeting calendar | federalreserve.gov scrape | none | CGI, MACRO |
| Company fundamentals | SEC XBRL | none (User-Agent) | FUNDAMENTALS |
| ETF holdings | State Street, then SEC N-PORT | none | FUNDAMENTALS |
| Commitments of Traders | CFTC Socrata | none | POSITIONING |
| Central bank press releases | RSS | none | POLICY |

**The FRED half now has a fallback.** `macro_data.FRED_IN_PRICE_HISTORY` maps
17 FRED ids to their AWS copies, so a FRED failure falls through to
DynamoDB. FRED is always tried first: it is the origin, and the two copies
agree exactly (checked 2026-09-27 — CPIAUCSL 334.131, GDP 32,486.066,
T10Y2Y 0.36, GDPNOW 5.0163 on both sides).

**The most fragile thing in the system is the fed funds futures leg.** It is
an unauthenticated Yahoo scrape behind a 6-hour cache, it has no AWS copy,
and every FOMC probability depends on it. If it breaks, the affected meeting
is returned with `available: false` rather than dropped — but there is no
fallback source.

### Storage

| Store | Shape | Size | Role |
|---|---|---|---|
| `cmon-stage-backend-price-history` | `symbol` + `date` | ~1,066,000 rows | **the record** |
| `cmon-stage-backend-metrics-source` | `source` + `symbol` | 249 rows | the registry — what the updaters fetch |
| `cmon-stage-backend-model-history` | `model_name` + `metrics_date` | 2,060 rows | daily regime quadrants |
| `cmon-stage-backend-regime-signals` | `signal_id` + `signal_date` | 22 rows | pre-registered flip probabilities and outcomes |
| S3 `Cache/macro/*.json` | one object per key | — | computed payloads, rebuildable |
| S3 `Cache/backtest/occurrences.json` | one blob | 6.1MB | every ticker × every regime occurrence |
| S3 `Dashboard/` | nightly .xlsx | — | the HUD workbook LIVE and TAPE read |

---

## 3. What updates when

25 scheduled EventBridge rules, all ENABLED (listed firsthand 2026-09-27).

| UTC | What |
|---|---|
| 23:59 | crypto prices |
| 23:00 | the brief → SNS (Sun–Thu daily, Sat weekly) |
| 00:05 | marketstack prices, FRED, US yields, GDP |
| 00:10 | Yahoo |
| 00:15 | inflation |
| 00:20 | derived metrics |
| 00:25 | compass, grid, and 6 clock models → `model-history` |
| 00:30 | dashboard workbook → `Dashboard/`; MTD report |
| 00:55 | regime signal updater → `regime-signals` |
| 01:00 | regime outcome backfill (1w/1m/3m realized) |
| 01:05 | regime divergence updater |
| 02:15 | alpha_vantage FX |
| 03:30 | backtest refresher → `Cache/backtest/occurrences.json` |

### The audit gap — state this plainly

**14 of those jobs have no source code in either local repo.** Everything
that feeds `price-history` — all the provider updaters and the model
updaters — lives in CodeCommit `cmon-stage-backend`. Nothing in
`cgi-vercel` or `market-dashboard` can build, review, or test them.

Source **is** in `market-dashboard/lambda/` for five: `backtest_refresher`,
`regime_signal_updater`, `regime_outcome_backfill`,
`regime_divergence_updater`, `cgi-brief-sender`.

### What is manual

46 symbols in `api/series_write.py` `ALLOWED` — every country macro series,
the Philippine curve, ISM, Challenger, BDI — are refreshed by a **Claude
routine, not by AWS**. No Lambda serves `source=tradingview`. The routine
runs monthly and pulls from TradingView's MCP.

`GET /api/freshness` is the worklist that drives it. A symbol added to
`ALLOWED` joins the routine automatically, which is the specific failure
that let 38 backtest tickers go unnoticed for a day: the list lived in one
place and the work in another.

---

## 4. The cache

S3-backed, one JSON object per key under `Cache/macro/`. Staleness is
object age against a per-key TTL. The schema version travels as object
metadata, so a version check costs nothing extra.

TTLs run 6h (fast-moving: FOMC probabilities, countries, policy watch, the
daily brief, freshness) through 12h (rates, COT, technicals, liquidity), 24h
(themes, fundamentals, inflation, context tables) to 168h (dot plot, ETF
constituents, FOMC calendar).

**Bump schema versions through `cache.SCHEMA_FROM_MODULE`, never by hand.**
Six times in this build a correct change was deployed and served stale
because a version was not bumped. Four keys now read their version from a
constant beside the code being changed: `countries`, `context_tables`,
`freshness`, and both FOMC keys.

`get_or_fetch_bg` serves the previous value and refreshes behind it, used
where a cold build exceeds Vercel's server-component timeout: `fundamentals`
(~30s), `countries` (~80s), `brief` (~31s). It re-checks the version before
serving stale — without that, background refresh silently defeats a schema
bump, which happened.

---

## 5. When something looks wrong

### A number looks old

Check `GET /api/freshness`. It answers **are we behind the source**, not
**is this old** — different questions.

- `current` — we match the source. **A correct number can be very old.**
  PHCBBS has been 238 days old since BSP stopped publishing in February.
  This is not a fault and there is nothing to do.
- `behind` — the source has newer data. This is the real failure. For a
  manual symbol, run the TradingView pull.
- `value_disagrees` — our copy and FRED differ on the same date. Something
  is broken in one of them; find out which before trusting either.

### A page is slow

First hit after idle is a Render free-tier cold start, up to ~75s. Warm,
back-to-back: `/macro` ~3.1–3.6s, `/` ~2.4s, `/cgi` ~2.5s, `/tape` ~1.8s,
`/countries` ~0.8s, `/cot` ~1.1s.

**Measure back-to-back.** The instance spins down between requests, so
measuring one page, pausing, then measuring the next reports cold starts as
page cost. This produced a whole round of misattributed optimisation in this
build.

### A change deployed but the page did not change

Almost certainly a schema version that was not bumped. This has happened six
times. Check the module constant, not the table in `cache.py`.

### The backtest banner says tickers are missing

The refresher Lambda ran against a different ticker list than the API
declares. Worked example — on 2026-09-26 the banner reported 129 tickers
against 167 expected, naming 38.

Walking this tree finds it: the banner's own line said *"universe source:
unknown (blob predates the field)"*. The current handler always writes that
field, so the blob was written by an older build. The handler had been fixed
and zipped but **never uploaded** — there was no deploy script, so there was
nothing to forget to run. Fix: `market-dashboard/lambda/backtest_refresher/deploy.sh`,
then the dry run, then the real run. Afterwards `universe_source` must read
`api`; anything starting `fallback:` means Render was asleep and the Lambda
used its own bundled list.

---

## 6. Known limits

Stated here rather than discovered later.

- **Render free tier.** ~75s cold start for the first visitor after idle,
  0.1 CPU, and the instance runs in Oregon while the data is in
  ap-southeast-1, so every S3/DynamoDB read is a cross-Pacific hop. Kept
  deliberately: this is a personal instance.
- **No CME FedWatch comparison.** CME blocks automated access and their
  terms prohibit scraping. Our FOMC probabilities use the same method and
  will differ; there is no automated calibration against theirs.
- **GDP vintage replay is not done.** Replaying the flip history on
  first-print ALFRED data would change historical regime labels, so it is
  not done without an explicit decision.
- **Country × regime edge is not distinguishable from noise.** 7 of 250
  cells clear |t|>2 where chance alone predicts 12.5. COUNTRIES is
  monitoring, not signal. The regime effect itself is strong — 64% of the
  variance in those returns is the regime, 2.5% is the country.
- **`DFEDTARL` is not in `price-history`** and is not registered. The lower
  bound of the target range is reconstructed as upper − 25bp when FRED is
  unavailable, flagged per row as `lower_is_derived`.
- **No staleness alarm in CloudWatch.** `STALENESS_ALARM_DESIGN.md`
  specifies one measured on age. Age is the wrong measure — see §5 — so it
  was deliberately not built as designed.

---

## 7. Is this the standard for every project?

The **structure** generalises: where the data comes from, what keeps it
current, what is manual, what to do when it looks wrong, and what the known
limits are. Those five questions are worth answering for anything that runs
unattended.

The specifics do not generalise, and this document should not be turned into
a template until it has been used at least once during a real failure. A
runbook that has never been opened in anger is a guess about what future-you
will need to know.
