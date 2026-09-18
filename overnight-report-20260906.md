# Overnight report — 2026-09-06

Canary build: `GET /api/macro/rates`, per PHASE2_PLAN.md Variant C
(S3-as-cache). Built and tested locally only. **No deploy, no git commit**
— all new/changed files sit uncommitted in the working tree for review:
`api/main.py` (modified), `api/requirements.txt` (modified), `api/cache.py`
(new), `api/macro_data.py` (new).

---

## Status: endpoint built and verified working, with two real bugs caught and fixed along the way

### What was built

- `api/cache.py` — S3-backed cache (`head_object` staleness check →
  `get_object` on hit, `put_object` on miss/refresh), bucket
  `cmon-stage-backend-369568916817-ap-southeast-1-reports`, prefix
  `Cache/macro/`. TTL table matches PHASE2_PLAN.md's final per-key values
  exactly for the 5 keys this canary needs; the other 6 keys (for
  `/api/macro/growth` and `/api/macro/dot-plot`) are listed
  commented-out so this file stays the single TTL source of truth going
  forward rather than being redefined per-endpoint later.
- `api/macro_data.py` — ported fetch logic from
  `~/market-dashboard/macro_data.py` + `fomc_data.py`, **with local
  parquet caching stripped out entirely** (see design decision below).
  Returns plain dicts/lists, not DataFrames, matching Phase 1's approach.
- `api/main.py` — added `GET /api/macro/rates`, same
  `require_bearer_token` dependency as `/api/live`, two lines.
- `api/requirements.txt` — added `pandas`, `requests`, `yfinance`.
  `beautifulsoup4` was NOT added — the FOMC calendar scrape uses plain
  regex on the raw page text (`re.findall`), not BeautifulSoup, contrary
  to what I'd assumed going in from the general Phase 2 dependency notes.

### Design decision: stripped local caching from the ported functions entirely

The original `macro_data.py`/`fomc_data.py` functions each have their
own local-parquet cache with their OWN staleness windows (e.g.
`fetch_treasury_curve`'s internal cache is 24h, but PHASE2_PLAN.md's
locked TTL for this key is 6h). Importing and calling those functions
as-is (even wrapped in the new S3 cache) would create two overlapping
cache layers with two different TTL sets — the S3 cache might decide
"fetch fresh," call the original function, and get back a value that's
itself served from a stale local cache up to 24h old, silently
defeating the whole point of the tighter 6h S3 TTL.

Fix: the ported versions in `api/macro_data.py` have no local caching at
all — every call is genuinely live. The S3 cache in `cache.py` is now
the sole staleness authority. This is a clean separation, not a
workaround, and it's the only version of this design that actually
delivers on the TTL table's specific per-key values rather than silently
inheriting Streamlit's older, coarser ones.

One disclosed side effect worth knowing: this canary's test run did NOT
touch `~/market-dashboard/cache/*.parquet` (unlike an earlier session
concern about this) — since the ported functions have no cache-write
step at all, nothing in `~/market-dashboard/` was touched by this build
or its tests.

### Two real bugs found and fixed during testing (not just "it worked")

**Bug 1 — NaN in outer-merged series broke JSON serialization.**
`fetch_treasury_curve`/`fetch_spreads`/`fetch_fed_funds_range` all build
wide DataFrames from multiple series with slightly misaligned dates
(e.g. `HY_Spread` doesn't always update the same day as `T10Y2Y`),
producing `NaN` gaps. Plain `json.dumps` would have silently accepted
these (NaN is allowed by default), but Starlette's actual
`JSONResponse.render()` uses `allow_nan=False` and raised `ValueError:
Out of range float values are not JSON compliant` on the very first
test call. Fixed by converting NaN→`None` in `_df_to_records` before
returning.

**Bug 2 — my own diagnostic initially gave a false pass, then a stale
poisoned S3 cache entry masked the fix.** After fixing bug 1, the
endpoint still failed with the identical error. My first diagnostic
script used plain `json.dumps()` (default `allow_nan=True`), which
doesn't reproduce Starlette's stricter behavior — it reported everything
"OK" when it hadn't actually validated anything. Re-ran with
`allow_nan=False` explicitly and confirmed the Python-level fix was
correct... but the endpoint still failed. Root cause: the very first
(pre-fix) run had already written a **poisoned cache entry** —
`Cache/macro/spreads.json` in S3 contained 4,288 literal `NaN` tokens,
because `cache.py`'s own `set()` also used permissive `json.dumps`
without `allow_nan=False`. That stale object was still within its 12h
TTL, so the cache was correctly serving it — with bad data baked in from
before the fix existed. Fixed `cache.py` to write with `allow_nan=False`
too (fail fast on write, never persist bad data), then manually cleared
all 5 polluted S3 objects so they'd rebuild clean. Confirmed clean after.

This is worth flagging prominently before scaling this pattern to the
other two endpoints: **any cache-writing code needs to validate what
it's about to persist, not just what it's about to return** — a
silently-permissive write path can mask a real bug for the entire TTL
window, which for the 48h/7d keys in the other endpoints would be a
much longer blind spot than the 12h one caught here.

### Cache-hit verification: confirmed working, including the yfinance rate-limit case

- First request: 12.1s (cold, all 5 keys fetched live + written to S3),
  973KB response.
- Second request (immediately after): 1.8s, byte-identical response.
- Confirmed via `head-object` that **none of the 5 S3 objects' timestamps
  changed** between call 1 and call 2 — this is real proof of a cache
  hit, not just a latency coincidence. Specifically confirmed
  `fomc_probabilities` (the yfinance-dependent key, the actual point of
  its 6h TTL being a "rate-limit safety margin") did NOT trigger a new
  yfinance call on the second request. This is the design's core claim
  and it holds.

### Streamlit field-by-field comparison: zero divergences

Ran the original `~/market-dashboard/macro_data.py`/`fomc_data.py`
functions directly (imported via `sys.path`, with `force=True` to bypass
their own local cache for a fair live-vs-live comparison — the
market-dashboard venv has a broken pyarrow/numpy install, architecture
mismatch, so this ran from the API's own venv with `pyarrow` installed
temporarily just for this comparison script, not added to
`requirements.txt`):

| Panel | Match? |
|---|---|
| `fed_funds_range` (latest: upper/lower) | ✅ exact (3.75 / 3.5) |
| `treasury_curve` (latest row, all 10 tenors) | ✅ exact |
| `spreads` (latest row) | ✅ exact — including the one real NaN case (`HY_Spread`), which correctly differs in representation (`nan` in the original DataFrame vs. `null` in the new JSON) but is the same underlying data gap, not a divergence |
| `fomc_meeting_calendar` | ✅ exact (`['2026-09-16', '2026-10-28']`) |
| `fomc_probabilities` (post_rate, p_cut/p_hold/p_hike, most_likely for both meetings) | ✅ exact, every field |

**Zero real divergences.**

### `fomc_probabilities` / `fomc_meeting_calendar` boundary decision

`get_upcoming_meetings()` (the calendar scrape + hardcoded 2026 list) is
cleanly separable from the probability computation — it produces a list
of meeting dates with no dependency on EFFR/futures/target-rate data.
Cached it as its own key (`fomc_meeting_calendar`, 7d TTL) and pass its
output as an input to `build_fomc_probabilities()`, which separately
fetches EFFR + fed funds range (for target rate) + yfinance futures and
computes probabilities (cached as `fomc_probabilities`, 6h TTL). No
overlap or awkward boundary — the two concerns were already naturally
separate in the original code, this just makes the separation explicit
via two cache keys instead of one function call.

### Plotly figure construction: deferred, not built

This canary returns raw data (records/dicts), not `fig.to_dict()`
Plotly figures. Chose to defer chart-figure construction because this
canary's actual purpose — proving the S3-cache mechanics, TTL
correctness, and data-fetch fidelity — didn't need it, and building 5
chart types now would have diluted focus from the two real bugs above,
which were far more important to catch early. Building the Plotly
figures is frontend-rendering-adjacent work better sequenced closer to
when the actual `web/` components get built, not blocking this backend
canary's review.

---

## TL;DR

**Endpoint built: yes.** `GET /api/macro/rates` in `api/main.py`
(2 new lines) + `api/cache.py` (new, ~90 lines) + `api/macro_data.py`
(new, ~280 lines) + `requirements.txt` (+pandas/requests/yfinance).
Nothing committed to git yet.

**Cache verified working: yes**, including the specific thing that
mattered most — confirmed no yfinance call fires on a cache hit within
the 6h TTL window (12.1s cold → 1.8s warm, S3 object timestamps
unchanged, byte-identical response).

**Streamlit match: zero divergences** across all 5 panels (fed funds
range, treasury curve, spreads, FOMC meeting calendar, FOMC
probabilities), verified by running the original functions directly and
diffing every field, not just spot-checking.

**Top 2 things needing your attention before scaling to the other two endpoints:**

1. **Two real bugs were caught and fixed in this canary** (NaN
   serialization, and a stale poisoned S3 cache entry masking the fix
   after it was made) — both are now hardened against (`allow_nan=False`
   on both read and write paths in `cache.py`), but this is exactly the
   kind of thing worth a second pair of eyes on before the pattern gets
   copy-pasted into `/api/macro/growth` and `/api/macro/dot-plot`,
   since those have longer TTLs (48h/7d) where a similar poisoned-cache
   bug would hide for much longer before anyone noticed.
2. **Plotly chart-figure construction was deliberately deferred** —
   this endpoint returns raw data, not chart-ready `fig.to_dict()`
   payloads. Worth confirming that's the right call before scaling,
   versus wanting figures built endpoint-by-endpoint as each one is
   canaried.

Nothing deployed, nothing committed, no Lambda or LIVE tab code touched.

---

# Session 2 (2026-09-05, later) — sanity_check() hook + growth/dot-plot endpoints

Continuing on the same uncommitted working tree. New files: `api/sanity_checks.py`,
`api/data_manual/dot_plot.csv` (copied static asset). Modified:
`api/cache.py`, `api/macro_data.py`, `api/main.py`. Still nothing
deployed, nothing committed, no Lambda/LIVE-tab/frontend code touched.

## Part A: sanity_check() hook — implemented and retrofitted

Added `api/sanity_checks.py` with the exact tiered spec: 12h/6h keys
(`fed_funds_range`, `treasury_curve`, `spreads`, `fomc_probabilities`)
skip checking entirely; 24h keys (`inflation`, `pce`, `gdp_nowcast`) get
presence+type+non-empty; 48h keys (`gdp`, `lending_standards`) add
value-range plausibility; 7d keys (`dot_plot`, `fomc_meeting_calendar`)
add structural checks (participant count/horizon count for the dot plot,
valid date parsing for the meeting calendar).

`cache.get_or_fetch()` was rewritten to route fresh fetches through
`sanity_checks.check()` before persisting: on failure, log an ERROR, do
**not** call `set()`, and fall back to whatever's in S3 already (even
past its TTL) via a new `_get_raw()` helper. If no prior cache exists at
all, log a second, more severe error and return the failed-check value
as a last resort rather than hard-failing the whole request.

**Retrofit onto the 5 `/api/macro/rates` keys**: re-tested after wiring
this in — `fomc_meeting_calendar`'s new structural check passes cleanly
against real data (2 real upcoming meetings, both valid dates), and the
other 4 keys correctly skip checking. The canary still returns identical
output to before the retrofit.

## Part A (bug found while building): the [-15,15]/[-100,100] checks were originally written wrong

First real test of `/api/macro/growth` (see below) hit a genuine sanity
check failure on `gdp` on the very first live fetch — not a deliberately
triggered test, an actual bug. `fetch_gdp_quarterly()` returns BEA's
**entire GDP history back to ~1950**, which legitimately contains real
outliers outside [-15%, 15%]: the 2020 COVID crash (-28.0% in 2020Q2,
+34.9% in 2020Q3) and a couple of 1950/1978 prints near 16.5%. My first
version of `_check_gdp` checked every row in the series, so it correctly
rejected... genuine, correct historical BEA data, because the range
check was applied to the wrong thing. Fixed: both `_check_gdp` and
`_check_lending_standards` now check only the **most recent** row, since
the actual intent ("is the newest print plausible") only ever needed
that one value — history is already known-good. Documented inline in
`sanity_checks.py` with the exact numbers that triggered it.

This is exactly the kind of thing worth surfacing plainly: the safety
mechanism itself had a bug on its first real-world exercise, caught
immediately by the fallback behavior working as designed (it correctly
refused to cache the "failure," logged loudly, and — since this was the
very first fetch with no prior cache — returned the value anyway per the
documented last-resort path, which is how this got noticed at all rather
than silently caching a value that then got silently rejected forever).

## Part B: `/api/macro/growth` — built, tested, one real pre-existing production bug found

All 5 keys built (`lending_standards`, `gdp`, `gdp_nowcast`, `inflation`,
`pce`), each `cache.get_or_fetch`-wrapped with its locked TTL and sanity
tier. `gdp` and `gdp_nowcast` confirmed cleanly separable per
PHASE2_PLAN.md's split — `fetch_gdp_quarterly()` (BEA T10101) and
`fetch_gdp_vintages()` (ALFRED) have zero dependency on `fetch_gdp_nowcast()`
(FRED GDPNOW) in the original source; no awkward boundary to reconcile,
same as the `fomc_probabilities`/`fomc_meeting_calendar` split in
session 1.

**Streamlit field-by-field diff: zero divergences on 4 of 5 panels**,
verified by running the original `macro_data.py` functions directly
against live data:

| Panel | Match? |
|---|---|
| `gdp` (quarterly + vintages) | ✅ exact (2026Q2: 1.5%, 48 vintage rows) |
| `gdp_nowcast` | ✅ exact (1.2392 / 1.54 / 4.7487 for the last 3 quarters) |
| `lending_standards` | ✅ exact (5.3 / 8.1 / 0.0 for the last 3 quarters) |
| `inflation` | ✅ exact to full float precision, all 3 series (CPI/Core CPI/PPI) |
| `pce` | ⚠️ **matches exactly — but the shared calculation is wrong** (see below) |

**Found a genuine pre-existing bug in production Streamlit, not
introduced by this port.** `pce_core_yoy` values came back as ~1.8
million instead of a sane ~2-3%. Traced it fully: `fetch_pce()`'s BEA
T20804 `DataValue` is a **chain-type price index level** (~126-130,
base=100 in some past reference period), not a MoM% change as the
function's own docstring claims ("Monthly PCE price index MoM% for
core"). `app.py`'s rolling YoY transform (`(1 + pce_core_pct/100)
.rolling(12).apply(lambda x: x.prod()-1) * 100`) assumes its input is
already a small decimal rate; fed an index level instead, compounding 12
values around 2.27 (`1 + 127/100`) produces exactly the ~1.8 million
result observed. **Confirmed this reproduces byte-for-byte in the
untouched original `~/market-dashboard/macro_data.py` + the exact
transform copied from `app.py:2728-2732`** — ran it directly, got
`1.800817e+06` / `1.834191e+06` / `1.844167e+06` for the last 3 months,
matching my port's `1800817...`/`1834191...`/`1844167.3452563952`
exactly. This means **the live Streamlit Core PCE chart is very likely
displaying nonsense values right now**, independent of anything to do
with Phase 2 — this predates this build entirely.

**Deliberately did NOT fix this in the port.** Given this session's
standing verification bar is "matches Streamlit field-for-field," I kept
the port byte-for-byte faithful to the buggy original rather than
silently diverging with what I think the "correct" calculation should
be (most likely: convert the index to MoM% via `.pct_change()` first,
*then* apply the 12-month compounding — but that's a guess at intent,
not something to decide unilaterally here). Flagging for your decision:
fix at the source (`market-dashboard/macro_data.py`, benefits both
Streamlit and this port), fix only in the Phase 2 port (diverges from
Streamlit, defeats the "should match" comparison going forward), or
leave as-is pending a real look at what BEA's T20804 field actually
represents.

## Part C: `/api/macro/dot-plot` — built, tested, exact match

Small as expected (~35 lines). Ported `fomc_data.load_dot_plot()`
verbatim, reading the same `data_manual/dot_plot.csv` (copied into
`api/data_manual/` as a bundled static asset). Verified against the real
file directly: 76 rows, 19 distinct participants, 4 horizons (2026,
2027, 2028, LR) — exact match, this is a straight file read with no
external API involved so there was no real chance of drift.

**On whether caching is redundant here**: built per spec (7d TTL +
structural check) as asked, but flagging as asked too — since this data
only ever changes on a redeploy (a manual CSV update requires a code
push regardless), the S3 cache round-trip adds a small bit of latency
(confirmed: 0.99s cold vs. 0.29s warm) for zero actual benefit over just
reading the bundled file directly on every request, which would be
sub-millisecond. Not fixing this unilaterally since it's explicitly
built-per-spec, but this is the one key where the caching layer is pure
overhead rather than solving a real problem (no external API to protect,
no meaningful staleness risk from a file that only changes on deploy).

## Sanity-check-failure-path proof (deliberate, not incidental)

Beyond the incidental real failure on `gdp` above, ran a controlled test
against `lending_standards`: recorded its cached value and S3
`LastModified`, force-fed `get_or_fetch()` a corrupted value
(`{"date": "2099-01-01", "value": 99999.0}`, `mock.patch`'d `cache.get`
to simulate a TTL-expired cache so the fetch path actually runs).
Confirmed all three things the design promises: (1) `sanity_checks.check()`
correctly rejects the corrupted value, (2) `get_or_fetch()` returns the
**original, pre-test cached value**, not the corrupted one, (3) the S3
object's `LastModified` timestamp is **byte-identical** before and after
— it was never touched. This is real proof, not an assertion.

## Cache-hit spot-checks for the two new TTL tiers

- `gdp` (48h): repeat call left `Cache/macro/gdp.json`'s `LastModified`
  unchanged (`2026-09-05T13:46:49Z` both times).
- `dot_plot` (7d): repeat call left `Cache/macro/dot_plot.json`'s
  `LastModified` unchanged (`2026-09-05T13:45:26Z` both times), and was
  visibly fast (0.29s) confirming a real cache hit, not just no visible
  side effect.

---

## TL;DR — Session 2

**Both endpoints built: yes.** `/api/macro/growth` (5 keys) and
`/api/macro/dot-plot` (1 key), both tested locally, both returning real
200s with real data. Nothing committed, nothing deployed.

**Sanity checks: implemented, retrofitted, and proven working** —
including a deliberate corruption test showing the cache correctly
refuses to overwrite good data with bad, with byte-identical S3
timestamps as proof. One real bug in the checks themselves was caught
and fixed during this build (range checks were being applied to entire
historical series instead of just the latest print, which meant the
very first live `gdp` fetch failed by correctly-but-wrongly rejecting
real 2020 COVID-era BEA data).

**Streamlit match: 9 of 10 new-panel fields exact; 1 has a shared,
pre-existing bug.** `gdp`, `gdp_nowcast`, `lending_standards`,
`inflation`, and `dot_plot` all match Streamlit field-for-field. `pce`
also "matches" — but only because I faithfully reproduced a **genuine
bug already in production Streamlit** (confirmed by running the
untouched original code and getting byte-identical garbage: ~1.8 million
instead of ~2-3% YoY). This is very likely visible in the live
Streamlit dashboard's Core PCE chart right now, unrelated to this build.

**Top things needing your attention before frontend work starts:**
1. **The Core PCE bug is real and predates this session** — decide
   whether to fix at the source (benefits both apps) or leave for now;
   I deliberately didn't fix it unilaterally since "match Streamlit" has
   been the standing bar all session.
2. **Dot-plot caching is technically redundant** (built per spec anyway)
   — a static bundled file doesn't need an S3 round-trip, but this is a
   minor efficiency note, not a correctness issue.
3. Both endpoints are ready for your review alongside the rates canary
   before any frontend/`web/` work begins, per your explicit stop point.

---

## MACRO frontend build (2026-09-06, follow-up session)

Built the Vercel MACRO tab frontend against all three now-deployed
backend endpoints (`/api/macro/rates`, `/api/macro/growth`,
`/api/macro/dot-plot` — confirmed `/api/macro/dot-plot` was already live
in production from the earlier commit, not a new deploy needed). Local
build + test only — nothing committed or pushed, nothing deployed,
`~/market-dashboard` untouched, existing LIVE tab code untouched.

### Route structure

New route `web/app/macro/page.tsx` (not a tab-switcher within the LIVE
page) — cleanest fit for Next.js App Router given MACRO's data model is
completely disjoint from LIVE's, and it lets each of the 3 backend
endpoints get its own independent `<Suspense>` boundary. Added a minimal
nav bar in `web/app/layout.tsx` (shared shell, not LIVE-page content) so
LIVE and MACRO are both reachable — there was no navigation at all
before this.

### Components built (`web/app/components/macro/`)

All 6 from PHASE2_PLAN.md's sketch, plus 3 supporting pieces:
- `PlotlyChart.tsx` — thin client wrapper (`next/dynamic`, `ssr:false`) since Plotly needs `window`
- `LineChart.tsx` — generic multi-series line/step chart (Fed Funds dual step-trace with fill, Spreads dual-y-axis, Inflation multi-line, Core PCE) with optional horizontal reference line
- `BarChart.tsx` — generic bar+line-overlay chart (GDP 3a/3b, Lending Standards QoQ)
- `DotPlotChart.tsx` — SEP dot plot's jittered-scatter-plus-median-bar, ported faithfully from `app.py:2233-2295`'s per-rate-level offset math
- `YieldCurvePanel.tsx` — 2-subplot layout (snapshot + 10Y history), hand-rolled `domain`-based subplot positioning since Plotly.js doesn't have `make_subplots`
- `FomcProbabilityPanel.tsx` — horizontal bar + meetings table
- `MetricStat.tsx` — small stat display (Streamlit `st.metric()` equivalent)
- `SectionHeader.tsx` / `ErrorCard.tsx` / `SectionSkeleton.tsx` — shared chrome for the 3 independent sections

Plus 3 async Server Components (`RatesSection.tsx`, `GrowthSection.tsx`,
`DotPlotSection.tsx`) that each fetch their own endpoint and catch errors
internally (render an inline `ErrorCard`, never throw) — this is what
makes the 3 sections genuinely independent, not just visually separated.

### Panel-to-chart mapping (ported from `app.py:2086-2765`)

Fed Funds Range (dual step-line + fill), FOMC Probabilities (bar +
table), SEP Dot Plot (custom jitter chart), Treasury Yield Curve
(2-subplot), Spreads (dual-axis), Bank Lending Standards (level +
QoQ-change bars), GDP (3a bars+GDPNow overlay, 3b grouped vintage
bars+diamond overlay, 3c GDPNow standalone), Inflation (multi-line + 2%
ref), Core PCE (single line + 2% ref, now showing the corrected ~3.3%
value from today's earlier fix).

### Dependencies added

`plotly.js-dist-min` + `react-plotly.js` (frontend, as anticipated) plus
`@types/react-plotly.js` + `@types/plotly.js` (dev, needed because
`react-plotly.js` ships no bundled types) — the only additions beyond
what PHASE2_PLAN.md anticipated.

### Testing — real, not skipped

1. `npx tsc --noEmit` clean, `npm run build` clean (had to work around
   several `@types/plotly.js` strictness issues with dynamically-built
   shapes/annotations/axis-refs — resolved via targeted `as Partial<Layout>`
   casts at the layout boundary rather than fighting each literal type;
   noted here since it's a real deviation from "clean idiomatic types"
   worth knowing about, not hidden).
2. Ran the actual stack: `uvicorn` (local `.env` token) + `next dev`,
   fetched `/macro` for real. **1,026,829 bytes**, HTTP 200, confirmed
   exact production values embedded verbatim in the rendered output:
   `pce_core_yoy: 3.3441430040338282` (today's PCE fix, correct),
   `gdpnow: 4.7487`, Fed Funds `"3.50% – 3.75%"` with real date, GDP
   vintages (`Advance`/`Second`/`Third` all present), dot plot
   (`projected_rate` × 6 distinct references), participant count text.
3. **Proved per-section independence, not just asserted it**: temporarily
   pointed `RatesSection` at a nonexistent path to force a real 404,
   re-fetched the page — confirmed `ErrorCard` rendered with the actual
   error message (`"API request failed: 404 Not Found..."`), while
   `lending_standards`/GDP/dot-plot data all still rendered correctly in
   the same response, completely unaffected. Reverted immediately after
   (file restored, confirmed via `git diff` showing no changes).

### Deviations from a strict 1:1 Streamlit port

- Hover-template details (Streamlit's `customdata`-based hover text
  showing quarter labels + release dates + formatted values on the GDP
  vintage chart) were not ported with full fidelity — Plotly.js supports
  this but it added meaningful complexity for a first pass; charts render
  correctly with default hover behavior instead. Flagging as a polish
  item, not a data-correctness issue.
- `fomc_meeting_calendar` (its own cache key/endpoint field) isn't
  rendered as a standalone UI element — Streamlit doesn't have a distinct
  panel for it either; it's consumed internally to compute FOMC
  probabilities, which is what's actually displayed. No functionality
  gap versus Streamlit, just noting the field exists in the API response
  without a 1:1 visual counterpart.

### Housekeeping

Added `*.tsbuildinfo` to `.gitignore` (build-cache artifact that
shouldn't be committed, same reasoning as the earlier `.deploy-tmp/`
exclusion).

**TL;DR**: MACRO frontend fully built (6 components + 3 section
wrappers + 1 route), `tsc`/`next build` both clean, real full-stack test
against real production-matching data (exact PCE/GDPNow values verified
embedded), per-section independent error handling proven with a real
forced-failure test (not just code review). Two known, minor,
non-blocking gaps: hover-template polish and `.tsbuildinfo` now
gitignored. Nothing committed, nothing deployed, LIVE tab and
`~/market-dashboard` both untouched. Ready for review before commit/push.
