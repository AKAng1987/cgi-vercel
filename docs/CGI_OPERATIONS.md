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

### Can the manual symbols be automated? Mostly no — audited 2026-10-03

The question worth answering, because the manual half is the half that
stops when the token budget does. Every one of the 56 was checked against
FRED directly rather than assumed.

**FRED has retired its OECD international republication.** The series that
would have replaced the country macro are all discontinued:

| what it would have replaced | FRED series | last observation |
|---|---|---|
| JP CPI | `JPNCPIALLMINMEI`, `CPALTT01JPM657N` | **2021-06** |
| GB broad money | `MABMM201GBM189S` | **2013-12** |
| JP M2 | `MYAGM2JPM189S` | 2017-02 |
| KR M2 | `MYAGM2KRM189S` | 2017-05 |
| CN M2 | `MYAGM2CNM189N` | 2019-08 |
| KR CPI | `CPALTT01KRM657N` | 2024-03 |
| GB CPI | `CPALTT01GBM657N` | 2024-02 |
| CN CPI | `CHNCPIALLMINMEI` | 2025-04 |

**Only two could move, and both did (2026-10-04).** `JP_CB_ASSETS` reads `JPNASSETS`
(x10^8, 100M yen) and `EU_CB_ASSETS` reads `ECBASSETSW` (x10^6, millions of EUR, **weekly**).
Both were already maintained nightly by the FRED Lambda, so no backfill or registration
was needed; `country_data.FRED_SCALED` applies the scale and falls back to the held copy.
Each factor was asserted equal to the stored value on shared dates first.

Comparing the old and new paths caught a real bug: `_bars_per_year` classed any spacing
of 10 days or less as daily, so a weekly series looked back 252 *bars* (about five
years) for "a year ago". EU would have printed -30.27% instead of -2.86%. Weekly is now
its own class.

Two more looked movable and were not, which is why the check matters:
`ECBDFR` is the ECB *deposit* rate and ours is the *main refinancing* rate (a constant
15bp apart), and FRED's Japan rate is the market call-money rate, not the BoJ target.

**The rest cannot move**: ISM is licensed, Challenger has no free API, the
breadth series are computed by TradingView itself, and the PH curve has no
free source. 54 symbols remain irreducibly dependent on a Claude session.

That is why the answer to "can the refresh stop needing tokens" is **no**,
and why the work went into making the routine's death *visible* (the
heartbeat) and *cheap* (`scripts/cgi_refresh.py`) instead.

### What is manual

54 symbols in `api/series_write.py` `ALLOWED` — the country macro series, the
Philippine curve, ISM, Challenger, BDI and the ten breadth series — are refreshed
by a **Claude routine, not by AWS**. No Lambda serves `source=tradingview`. The
scheduled task runs 09:30 Monday to Saturday, is script-driven
(`~/market-dashboard/scripts/cgi_refresh.py`), and writes a heartbeat that
`/api/freshness` reports; it is flagged stale after 48 hours.

`GET /api/freshness` is the worklist that drives it. A symbol added to
`ALLOWED` joins the routine automatically, which is the specific failure
that let 38 backtest tickers go unnoticed for a day: the list lived in one
place and the work in another.

### Alerts to CTS Ideas (built, awaiting a token)

`cgi-cts-poster` (Lambda, EventBridge `cgi-cts-poster-daily`, 02:30 UTC) posts regime
flips and theme starts/ends to the CTS Ideas feed. No Claude in the loop, no CGI secret:
it reads the public `/api/brief` and `/api/watchlists` proxies. **It is deployed with
`DRY_RUN=1` and posts nothing.** To go live: a CTS admin mints an agent token (Admin >
Agents > + New); add it as `CTS_AGENT_TOKEN` **and set `CTS_MCP_URL`** (the CTS service address, from their
connection doc; it has no default and is not in the code because this repo is public) in the Lambda
*console* (the CLI replaces the whole environment map and would wipe `DRY_RUN`); read one dry-run log;
set `DRY_RUN=0`. A live run without the URL fails loudly before doing anything.
A regime post is short text plus ONE picture, the regime card, drawn by the app at `/share/regime.png`
(CTS's server fetches that public URL and re-hosts it), and links to the app and to the `CGI · now` TradingView list
(the best/worst 20 live there, not in the text). The poster pre-flights the picture (200, a real PNG, under 5MB) and
leaves it off rather than fail the post. Handy calls: `{"selftest": true}` (read-only: signs in, `whoami`),
`{"replay": {"kind": ..., "when": ...}, "preview": true}` (shows the exact post, posts nothing; `"repost": true`
bypasses only the already-posted check), `{"inspect": "<postId>"}` (what CTS actually stored, e.g. the image count).
Its first live run seeds its state and posts nothing. De-dup state is
`State/cts_alerts_posted.json`; a state read that fails for any reason except "not found"
raises rather than re-seeding. Code and tests: `~/market-dashboard/lambda/cgi-cts-poster`.

### The refresh routine must reach the API through Vercel, not Render

The routine runs on the user's own machine, and the networks that machine sits on (office and home)
**sinkhole `*.onrender.com`**: DNS answers with a private `192.168.x` address, so every call fails with
"Network is unreachable", while `vercel.app` stays reachable. On 2026-10-05 the first weekday run failed this
way, stopped as its rules say, wrote no heartbeat and still reported "succeeded": the session finished, it
just did nothing. So everything the routine calls goes through a same-origin Vercel proxy:
`/api/freshness`, `/api/freshness/heartbeat`, `/api/series/<symbol>` and `/api/watchlists`, and
`scripts/cgi_refresh.py` defaults to the Vercel host (pinned by a test). A new endpoint the routine needs
must get a proxy first. Diagnose with `host cgi-api-9mim.onrender.com`: a `192.168.x` answer is the sinkhole.
`~/cgi-mcp` (the read-only tool for the execution project) also goes through Vercel by default, via
`/proxy/<api path>`: a GET-only passthrough that forwards the caller's own bearer token to Render, so the
login-protected endpoints stay protected; only the paths cgi-mcp uses are allowed (never the write endpoints).

### TradingView lists stay in sync (write only on change)

Nothing in AWS can write to TradingView, so the three lists (`CGI · now`, `CGI · if next flips`,
`CGI · earning it`) are rewritten by the same scheduled task as the series refresh, **after** its
heartbeat so a list problem can never stop the heartbeat. `scripts/cgi_refresh.py lists plan` diffs
`/api/watchlists` against `~/.cgi/tv_lists_state.json` (what was last written) and prints remove/add
arrays only for lists that differ; the normal outcome is "unchanged" and **no TradingView call**.
`lists done ID=HASH` records a write and refuses if the API moved since `plan`. On Saturdays the task
reads the lists back and `lists verify` repairs drift (a manual edit, an interrupted rewrite: the tools
cannot replace a list, so a rewrite is remove-then-add and is not atomic). The first run that uses the
watchlist tools may pause on a tool-approval prompt: click "Run now" once to pre-approve them.
The earning-it list excludes OTC names (read from the SEC file at run time).

### Feed integrity: does the registry agree with the data

`/api/freshness` -> `feed_integrity` catches three failures that each silently starved a
series and were each found by eye:

| failure | meaning | example |
|---|---|---|
| orphan | registered under `tradingview` (no Lambda serves it) but not in `ALLOWED` | MAGS, UUP |
| collision | two symbols share one `(source, source_symbol)`; the updater keys on source_symbol, so only one is fed | URA vs URANIUM |
| stalled | a backtest-universe ticker whose newest bar is more than 5 sessions behind (FRED rows: 14 days, for the weekly H.10 lag) | PBS, JJC, JJN stopped in 2023 |

If the check cannot run it reports itself as a problem rather than a healthy zero. The
brief's freshness section lists whatever it finds. A FRED copy gets one night of grace
before it counts as behind (the copy runs once a night).

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

### A TradingView list will not load

Almost always a wrong EXCHANGE prefix: TradingView drops a symbol it cannot place without
saying so. Symbols come from `api/tv_symbols.json`, built by `scripts/build_tv_symbols.py`
from TradingView's own symbol search, and stocks from the SEC's ticker file; a ticker with no
verified symbol is left out and reported, never guessed (the old code answered `AMEX:` for
125 of 173 tickers). `check_api_imports.py` fails if a universe ticker has no symbol. After
fixing the API, the TradingView lists themselves still hold the old symbols until they are
rewritten from `/api/watchlists`.

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
- **The "Drivers" P(flip) is not a market price.** For inflation, growth and credit it is
  a table of how often the axis flipped when each driver sat in its current tercile, cut
  over the same history the drivers were chosen on (in-sample), with readings taken at
  publication lags. Only liquidity has a real market read (fed funds futures). Reading
  monthly data by its stamped date had leaked the future and inflated the table.
- **A latent-state (Kalman) P(flip) was tested and not shipped** (2026-10-04,
  `research/latent_state/RESULTS.md`): no out-of-sample edge over the Markov base rate.
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
