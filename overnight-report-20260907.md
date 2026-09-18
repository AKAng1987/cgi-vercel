# Overnight Report — 2026-09-07

Scope: 4 read-only/non-destructive tasks per instructions. No deploys, no
code changes to `api/dashboard_data.py` / `api/macro_data.py`, no
production Lambda touches, no writes to `model-history`/`price-history`.

---

## TASK 1 — Page load speed diagnosis

### Measured numbers

**Warm** (Render already spun up), 3 runs each, from this machine:

| Page | time_total | TTFB | Response size |
|---|---|---|---|
| `/` (LIVE) | 4.5–5.4s | 0.43–0.53s | 168,501 bytes |
| `/macro` | 4.8–6.1s | 0.48–0.62s | 459,939 bytes |

**Cold** (Render free tier spun down after ~18 min idle):

| Test | time_total |
|---|---|
| Direct hit on Render root (`/`), cold | **75.5s**, then **75.8s** (two independent cold-starts, measured ~15 min apart — very consistent) |

First cold-start test was contaminated (pinged Render's root directly
*before* hitting the Vercel page, so Render was already warm by the
time the Vercel page's server-side fetch ran — that's why the Vercel
`/` request right after only took 5.1s despite Render having just been
asleep). Re-ran with a clean methodology — waited ~15 min with zero
traffic, then hit **only** the Vercel page directly as the first
request — but it came back in 5.3s, meaning Render was apparently
*still warm* at that point. (The background wait process that was
supposed to guarantee this got killed early by a host-level low-memory
event outside this task's control, so the actual idle gap achieved was
shorter and less certain than intended — likely 15–16 min, right at or
just under Render's free-tier spin-down threshold, rather than the
comfortable ~20 min margin planned.) Did not re-attempt a third time
tonight given the ~20 min cost per attempt; flagging as an open item
rather than guessing.

**What's already certain regardless of that re-test:** Render's free
tier cold-start is a consistent **~75 seconds**. Since `apiFetch()` in
`lib/api.ts` does a plain server-side `fetch` with no timeout override,
a real visitor hitting a cold instance would see the Vercel page hang
for the full ~75s before any HTML renders — Vercel's own default
function timeout (10s on Hobby plan, up to 60s on Pro) may even **abort
the request before Render finishes waking up**, which would surface as
a hard error/timeout page rather than a slow-but-working page. Checked
the repo for a `maxDuration` override (`vercel.json`, route segment
config) — **none exists anywhere**, so whatever the account's default
plan limit is applies unmodified. If this project is on Vercel's Hobby
tier (10s default), a cold Render visit is very likely **failing
outright with a function timeout right now**, not just loading slowly —
worth confirming the plan tier as a priority, since this would be a
correctness issue (visible error page) on top of the speed issue. This
is inferred from the ~75s Render number and the absence of any
`maxDuration` override, not directly observed end-to-end tonight (see
gap noted just above) — recommend a deliberate, longer-margin repro
(e.g. confirm 30+ min idle via Render's own dashboard/logs, then hit
the Vercel URL once) to turn this from "very likely" into "confirmed."

### Where the time actually goes — traced from the code, not guessed

**`/` (LIVE):** `build_live_response()` in `dashboard_data.py` does, in
order: `list_objects_v2` (paginated) to find the latest dashboard date →
one `get_object` for that day's `.xlsx` → `openpyxl.load_workbook()`
parse in-memory → parse 4 sheets (HUD/COMPASS/GRID/CLOCK) into dicts. No
DynamoDB calls in the common path (`model_history_fallback` is a
last-resort fallback only triggered if a sheet's quadrant cell is
blank). Bottleneck candidates here: the S3 list+get round trip, and
`openpyxl` parsing a multi-sheet workbook synchronously. This path is
already close to minimal — one S3 read, not many.

**`/macro`:** each of the 3 backend endpoints (`rates`, `growth`,
`dot-plot`) is fetched independently by its own React Server Component
under its own `<Suspense>` boundary — those 3 run **concurrently**, that
part is fine. The problem is *inside* each endpoint:

- `build_rates_response()` makes **5 sequential, blocking**
  `cache.get_or_fetch()` calls (`fomc_meeting_calendar`,
  `fed_funds_range`, `fomc_probabilities`, `treasury_curve`, `spreads`)
  — none are parallelized (no `asyncio.gather`, no threading). Same
  pattern in `build_growth_response()`: 5 sequential calls
  (`lending_standards`, `gdp`, `gdp_nowcast`, `inflation`, `pce`).
  **Yes — confirmed: S3 cache reads are serial, not parallel**, exactly
  the suspicion in the task brief.
- Cross-region latency compounds this: the S3 bucket
  (`cmon-stage-backend-...-reports`) lives in `ap-southeast-1`
  (Singapore); Render's free tier defaults to Oregon (US West). Every
  one of those 9 sequential S3 round trips pays cross-Pacific latency
  (~200–300ms each based on typical Singapore↔Oregon RTT), so even on a
  100% cache hit, `rates` alone is doing ~5 × 250ms ≈ 1.25s serialized,
  and `growth` another ~5 × 250ms ≈ 1.25s serialized (in parallel with
  rates, so `/macro`'s floor is set by whichever of the two is slower,
  not the sum — still ~1.25–1.5s minimum before any actual data
  processing or rendering).

### A bigger finding than expected: several cached payloads are wildly overfetched

Checked the actual S3 cache objects directly (all within TTL right now,
so these are exactly what today's warm-load numbers above are
transferring and parsing):

| Cache key | Size | Rows | What the frontend actually uses |
|---|---|---|---|
| `treasury_curve.json` | **730 KB** | 5,000 (full daily history since 2006-09-11, 10 tenors) | 3 snapshot rows (latest/6M/1Y) + one tenor's full history line for the right-hand chart |
| `spreads.json` | **297 KB** | 5,038 (full daily history since 2006-09-11) | All 5,038 points rendered directly, no windowing in `RatesSection.tsx` either |
| `fed_funds_range.json` | 96 KB | — | one current value + a step-chart |
| `inflation.json` | 46 KB | — | one line chart |

`treasury_curve.json` and `spreads.json` together are **~1 MB of the
~1.2 MB total S3 payload** `/macro` fetches server-side, and neither is
trimmed before caching or before rendering — `YieldCurvePanel.tsx` and
`RatesSection.tsx` both consume the full un-windowed arrays. The
20-year daily yield curve matrix is being cached, transferred
S3→Render, JSON-parsed, shipped Render→Vercel, and then Plotly renders
~5,000 points on a line chart — for a panel that only visually needs 3
point-in-time snapshots plus one reasonably-recent history line (the
original Streamlit panel may have intentionally shown full history —
worth confirming intent before trimming, flagged as a proposal not an
assumed bug).

Plotly itself (`plotly.js-dist-min`, client-side, dynamically imported
with `ssr:false` — correctly not blocking SSR) is a heavy bundle
(~350KB+ gzipped) and `/macro` instantiates it 8+ times (LineChart ×4,
BarChart ×3, DotPlotChart, YieldCurvePanel). First-visit hydration cost
for that many chart instances is real but secondary to the payload-size
issue above.

**No ISR/caching configured on the Next.js side at all** —
`next.config.mjs` is the default empty config, and `apiFetch()` in
`lib/api.ts` hard-codes `cache: "no-store"` on every request. Every
single page view re-runs the entire server-side fetch chain from
scratch, even though the underlying S3 cache TTLs are 6–168 hours. This
means the *actual* data almost never changes between visits, but every
visitor pays the full fetch cost anyway.

### Fixes, ranked by impact/effort

1. **Trim `treasury_curve` and `spreads` before caching** (highest
   impact, moderate effort — touches `api/macro_data.py`, which is
   explicitly off-limits tonight; flagging as the top recommendation for
   the next work session). Cutting ~1MB down to what's actually rendered
   would likely cut `/macro`'s S3 transfer+parse time by more than half,
   and benefits *every* load, warm or cold, cache-hit or cache-miss.
2. **Add Next.js ISR** (`export const revalidate = <seconds>` on
   `page.tsx` and `macro/page.tsx`, or per-section on the async Server
   Components) matched to the shortest relevant TTL (6h for rates data).
   Low effort, high impact for repeat visitors — turns "everyone pays
   full fetch cost" into "one visitor per revalidate window pays it."
   Needs review since `cache: "no-store"` was presumably chosen
   deliberately (worth confirming why before changing).
3. **Parallelize the sequential `cache.get_or_fetch()` calls** inside
   `build_rates_response()` / `build_growth_response()` (e.g.
   `ThreadPoolExecutor` since these are sync boto3 calls, or a genuine
   async rewrite). Removes ~1s of pure network-wait serialization per
   endpoint. Also off-limits tonight (same two files), noted for later.
4. **Render keep-warm ping** (cron hitting `/api/health` every 10 min).
   Solves the cold-start tax specifically but does nothing for the
   ~4–6s *warm* load time shown above — the warm numbers are already the
   bigger, more universal problem. Worth doing, but not the first thing.
5. Chart lazy-load / defer non-visible sections: lower priority — the
   Suspense-per-section architecture already gives progressive reveal;
   the actual cost is payload size and hydration count (item 1/3 above),
   not lack of lazy-loading per se.

**Concrete recommendation for biggest perceived-speed win:** trim the
two oversized cache payloads (`treasury_curve`, `spreads`) to what the
UI renders. It's the only fix that helps *every* load — cold, warm,
cache-hit, cache-miss — and it's the single largest, most unambiguous
number found tonight (~1MB of a ~1.2MB S3 payload is unused history).
ISR (#2) is the best "5-minute fix" if a code change to the two
off-limits files isn't wanted yet.

---

## TASK 2 — Regime signal historical data quality audit

Read-only DynamoDB query, full history, both series, from
`cmon-stage-backend-model-history`:

| Series | Rows | Date range | Duplicate `metrics_date` | Null/missing quadrant | Out-of-range quadrant |
|---|---|---|---|---|---|
| `compass_US` | 71 | 2004-07-01 → 2026-08-03 | 0 | 0 | 0 (all values in {1,2,3,4}) |
| `grid_US` | 143 | 2008-03-27 → 2026-07-30 | 0 | 0 | 0 |

**Important structural note for Markov training:** neither table is a
daily/periodic series — each row is written on an *event* (an
underlying signal changing enough to warrant a new snapshot), not on a
calendar cadence. `grid_US` clusters at roughly quarterly (~90–120 day)
intervals, consistent with GDP-release-driven updates. `compass_US` is
irregular, driven by Fed funds range changes and bank lending survey
(DRTSCILM) prints. **"Date gaps > 5 business days" is not a meaningful
staleness signal for this table** — nearly every gap exceeds 5 business
days by design. Reporting actual gaps for context instead:

- `compass_US` largest gap: **987 days**, 2009-01-17 (Q2) →
  2011-10-01 (Q1). This spans the ZIRP-era Fed hold and a long stretch
  of flat bank-lending-standards data — plausibly a genuine "nothing
  crossed a threshold" period, but it's by far the largest gap in either
  series and worth a manual sanity check before Markov trains on it (a
  987-day dwell time in one implicit state is a lot of weight on one
  transition-probability estimate if the model treats gaps as duration).
- `compass_US` second-largest: 456 days (2014-04-01 → 2015-07-01).
- `grid_US` gaps are far more uniform: largest is 154 days
  (2008-09-26 → 2009-02-27), most cluster at 90–120 days — consistent
  with the quarterly-cadence hypothesis, no obvious outlier.

**Quadrant transitions:** checked for "impossible jumps" — every
transition type between all 4 quadrants of `grid_US` occurs multiple
times in the data, including "diagonal" transitions where both axes
flip in one recorded step (e.g. `1→4`: 17 times, `4→1`: 12 times,
`2→3`: 22 times, `3→2`: 21 times — these are actually *more* frequent
than some "adjacent" transitions). Given the event-driven, non-daily
write pattern, a diagonal jump is not evidence of corruption — it's
consistent with two independent underlying signals (e.g. growth print +
inflation print landing in the same reporting window) both moving
between infrequent snapshots. No transition looks structurally invalid.

**Cross-check against LIVE tab — consistent, no divergence found:**

| | model-history latest row | LIVE tab (`/api/live`) |
|---|---|---|
| Compass | 2026-08-03, Q2 | quadrant=2, since=2026-08-03 ✓ |
| Grid | 2026-07-30, Q4 | quadrant=4, since=2026-07-30 ✓ |

**Cleanup recommendation before Markov training:** none required for
data integrity (no dupes, no nulls, no invalid values, LIVE-tab
consistent). The one thing worth a human decision, not a cleanup, is
how the training pipeline should treat the 987-day compass gap — as a
987-day dwell in Q2, or as a data question worth double-checking against
Lambda run history from that era before trusting the duration.

---

## TASK 3 — Track-record log table creation

Table did not exist (`describe-table` returned `ResourceNotFoundException`
before creation). Created successfully — **not** classifier-blocked, ran
directly:

```
aws dynamodb create-table \
  --table-name cmon-stage-backend-regime-signals \
  --attribute-definitions \
      AttributeName=signal_id,AttributeType=S \
      AttributeName=signal_date,AttributeType=S \
  --key-schema \
      AttributeName=signal_id,KeyType=HASH \
      AttributeName=signal_date,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region ap-southeast-1
```

**Result:**
- **Status:** `ACTIVE`
- **ARN:** `arn:aws:dynamodb:ap-southeast-1:369568916817:table/cmon-stage-backend-regime-signals`
- **Billing:** `PAY_PER_REQUEST` (on-demand, as specified)
- **Keys:** `signal_id` (HASH, String) / `signal_date` (RANGE, String)
- **No LSI/GSI**, as specified
- **Item count: 0** — no data written, per instructions

Schemaless attributes (`timestamp_utc`, `regime_current_discrete`, etc.)
were **not** written anywhere — table is empty, ready for the Markov
signal-logging code whenever that's built.

---

## TASK 4 — FRED FX stall pre-check (Monday 2026-09-08 trigger)

Hit `fredgraph.csv` directly for all 11 `DEX*` series (pulled the exact
list fresh from `metrics-source` rather than trusting memory):

| Series | Latest non-null observation |
|---|---|
| DEXCHUS, DEXHKUS, DEXINUS, DEXJPUS, DEXKOUS, DEXSIUS, DEXSZUS, DEXTHUS, DEXUSAL, DEXUSEU, DEXUSUK | **2026-08-28** (all 11, no exceptions) |

**Sanity check that this is FX-specific, not FRED being down
site-wide:** pulled `DFF` (one of the 13 non-FX FRED macro series) —
current through **2026-09-03**. Confirms the freeze is isolated to the
`DEX*` FX series specifically, matching the memory record exactly (no
new information suggesting it's resolving).

**Conclusion: still frozen. Prepare the source-swap plan — Monday's
decision should go ahead as "swap," not "wait."**

**Alpha Vantage quota math — correction to prior estimate:** memory
recorded "~14 headroom" for adding 11 DEX pairs against the 25/day free
tier. Checked the *current* `alpha_vantage` rows in `metrics-source`
directly rather than trusting that number: **4 symbols already on
Alpha Vantage today** (IDR, PHP, RUB, TRY). So the real math is:

```
4 (existing AV calls/day) + 11 (new DEX pairs) = 15 calls/day
25/day free tier − 15 = 10 headroom, not 14
```

Still survives the free tier (10 calls of daily headroom), but tighter
than the number in memory — worth knowing before committing to this as
the long-term plan rather than a stopgap, since 10 headroom leaves less
room for future FX additions than previously assumed.

---

## TL;DR

1. **Speed:** Render's cold-start is a solid, twice-measured **~75
   seconds** — and with no `maxDuration` override anywhere in the repo,
   a cold visitor on Vercel's likely default timeout may be seeing a
   hard error, not just a slow page (inferred, not directly observed —
   flagged for a deliberate follow-up test). Separately, confirmed both
   suspicions in the brief on the *warm* path — S3 cache reads **are**
   serial (5 sequential blocking calls per macro endpoint), and there's
   zero ISR/caching on the Next.js side (`cache: "no-store"`
   everywhere). But the **single biggest number found tonight** is that
   `treasury_curve.json` (730KB) and `spreads.json` (297KB) — full
   20-year daily histories — make up ~1MB of `/macro`'s ~1.2MB S3
   payload, and neither is trimmed before the frontend renders only 3
   snapshot rows + one history line from each. **Recommend fixing that
   first** — it's the only fix that helps every load, cold or warm.
2. **Data quality:** `compass_US` (71 rows) and `grid_US` (143 rows)
   are both clean — no dupes, no nulls, no invalid quadrants, and both
   match the LIVE tab exactly. Not daily series though — event-driven
   writes, so "gap > 5 business days" isn't a meaningful check; flagged
   the one real outlier (987-day compass gap, 2009–2011) for a human
   look before Markov trusts it as dwell time.
3. **Table created:** `cmon-stage-backend-regime-signals` is live,
   empty, on-demand billing, correct keys — ready for Markov to write to
   whenever that code exists. Not classifier-blocked.
4. **FRED FX:** Still frozen at 2026-08-28 across all 11 pairs (confirmed
   FX-specific, not FRED-wide). Monday's call should be "swap to Alpha
   Vantage," not "wait." One correction to prior math: real AV headroom
   after adding all 11 is **10 calls/day, not 14** — 4 are already spoken
   for.

Nothing deployed, nothing written to `model-history`/`price-history`,
`api/dashboard_data.py` and `api/macro_data.py` both untouched.
