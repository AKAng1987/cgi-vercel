# Vercel Phase 3 — BACKTEST tab port

Status: **plan only, no code yet**. Grounded in a direct read of
`~/market-dashboard/app.py`'s `BACKTEST` tab block (`elif active_tab ==
"BACKTEST":`) and `backtest_engine.py` — not designed blind. Mirrors the
Phase 2 MACRO pattern (`PHASE2_PLAN.md` Variant C: S3-as-cache) where it
still fits, and departs from it explicitly where BACKTEST's compute
profile doesn't.

## What the Streamlit tab actually does (from source, not memory)

Confirmed by reading `app.py:1096-1296` and `backtest_engine.py` in full:

- **Regime timeline**: `data_cache.load_model("grid_US")` +
  `load_model("compass_US")` (full `cmon-stage-backend-model-history`
  event log per model, no date bound) →
  `backtest_engine.build_regime_periods()` walks the merged change-event
  dates and emits one row per `(start, end, grid_q, compass_q)` interval.
  This is the same `model-history` table Phase 1's LIVE tab already
  reads, just consumed as a full event log rather than "latest row."
- **Price universe**: `BACKTEST_UNIVERSE` = every ticker in `app.py`'s
  `HUD_GROUPS` (the same universe `dashboard_data.py` already ports for
  the LIVE tab) **minus** `{"US INTEREST RATES", "SPREADS", "RATES",
  "FOREIGN RATES"}` — roughly 130-140 symbols. For each, `data_cache.
  _fetch_price_raw()` runs an **unbounded** paginated Query against
  `cmon-stage-backend-price-history` (no date filter, no limit) — full
  history, e.g. SPX alone is ~24,800 rows.
- **Compute** (`backtest_engine.py`, all in-memory pandas, no further
  AWS calls once data is loaded): for a selected `(grid_q, compass_q)`,
  `get_occurrences()` filters each matching period's price rows via a
  boolean date mask, takes entry/exit close + period high/low, and
  `compute_stats()` aggregates across occurrences into Occurrences /
  Avg High% / Avg Low% / Hit Rate / **Edge** (`avg_high / |avg_low|`,
  the audited formula — do not touch) / Avg Return%. `build_backtest_table()`
  runs this per ticker across the whole universe and sorts by Edge.
  `deep_dive_grid()` (DEEP DIVE tab, same engine) runs it for one ticker
  across all 16 combos.
- **User controls**: Compass Q / Grid Q selectors, min-occurrences slider
  (1-20), group multiselect filter, lookback radio (All / 10y / 5y —
  filters `periods_df` by start date before matching). All four are
  cheap filters on already-computed data, not separate fetches.
- **Occurrence detail**: an expander re-runs `get_occurrences()` for one
  selected ticker and lists every individual occurrence (dates,
  duration, High%/Low%/Close%).
- **Shared engine, out of scope but noted**: DEEP DIVE's 4×4 edge grid
  and SCENARIO's `get_scenario_occurrences()`/`build_scenario_table()`
  use this exact same engine and the exact same two data sources. This
  plan scopes BACKTEST only per your ask, but the cache design below is
  built so DEEP DIVE/SCENARIO can reuse it later without redoing the
  expensive part twice — see "Risks + open decisions."

## The one finding that shapes this whole plan

Unlike MACRO (a cache miss triggers a handful of small FRED/BEA calls,
seconds), a BACKTEST cache miss would mean pulling **full price history
for ~135 symbols** via unbounded per-symbol DynamoDB queries — tens of
thousands of items total. That's not a "slow request," it's a request
that risks blowing past Render's free-tier request timeout outright,
compounded by the already-measured ~75s cold start. **The fix is to
never let a user's page load be the thing that pays this cost** — see
"Compute concern" below for the concrete design consequence.

---

## 1. Data sources

- `cmon-stage-backend-model-history` (`grid_US`, `compass_US`) — full
  event log, read once per cache-refresh cycle, not per request.
- `cmon-stage-backend-price-history` — full per-symbol history for the
  ~135-symbol BACKTEST universe, same unbounded-Query pattern as
  Streamlit's `_fetch_price_raw`. This is the expensive read; see below.
- No FRED/BEA/BLS/AV involvement — this tab is 100% internal DynamoDB
  data, no third-party rate-limit or soft-error concerns like MACRO had.

## 2. API endpoint shape

Two public read endpoints, mirroring the MACRO sub-endpoint pattern,
plus one protected refresh endpoint (new pattern, justified below):

- `GET /api/backtest/table?grid_q=&compass_q=&min_occ=&lookback=` —
  returns the sorted per-ticker stats table for one regime combo.
- `GET /api/backtest/occurrences?ticker=&grid_q=&compass_q=` — returns
  the occurrence-detail list for one ticker/combo (powers the expander).
- `POST /api/backtest/refresh` (bearer-token protected, same
  `API_TOKEN` dependency as everything else) — rebuilds the cached
  occurrence dataset from DynamoDB. Not called by the frontend at all;
  called out-of-band once a day. See "Deployment"/"Risks" for the
  trigger mechanism, which is an open decision for you.

**Why cache occurrence-level data, not the final aggregated table:**
the expensive step is walking full price history into occurrence rows
(`get_occurrences`); the cheap step is aggregating occurrences into
stats (`compute_stats` — a few pandas `.mean()`/`.sum()` calls) and
applying `min_occ`/`lookback` filters. Caching one JSON blob of
`{ticker: {combo: [occurrence rows]}}` for all 135 tickers × 16 combos
means every `min_occ`/`lookback` combination the user picks is served
by re-aggregating already-loaded cache data — no DynamoDB touched, no
per-request recompute of the heavy part. Rough size: total occurrence
rows ≈ tickers × total historical periods (periods_df has on the order
of 100-250 rows total across all 16 combos combined, not per ticker) ≈
135 × ~200 ≈ 27,000 small records — likely low hundreds of KB as JSON,
comfortably S3-cacheable, nowhere near the ~1MB MACRO payload flagged
as oversized in the 2026-09-06/07 audit.

## 3. S3 cache strategy

Single cache object, `Cache/backtest/occurrences_all.json`, holding the
full precomputed occurrence dataset. Unlike MACRO's per-panel TTL
tiering (different upstream data changes at different cadences),
BACKTEST has exactly one invalidation trigger: **did today's daily
price close land, or did a regime period change** — both are same-day,
single-cadence events. One TTL is sufficient; no tiered sanity-check
logic like MACRO's 24h+ keys need, since this data isn't sourced from a
flaky third-party API — it's internal DynamoDB, already covered by the
silent-failure patches on the ingest side.

## 4. TTL per cache key

`occurrences_all`: **24h**, refreshed by the protected `/refresh`
endpoint rather than lazily on a public-endpoint miss (see below). If a
lazy-fallback path is wanted for resilience, it should still never be
the *primary* refresh mechanism.

## 5. Frontend components

**Reusable as-is or near-as-is:**
- `lib/api.ts` `apiFetch` — same server-side bearer-token fetch pattern.
- `HudTable.tsx`'s grouped-header treatment — the Streamlit BACKTEST
  tab's inline group-divider markup (`background:#1a1f35;color:#8b9dc3;
  ...`) is byte-for-byte the same styling `HudTable.tsx` already uses
  for its own group headers. A new `BacktestTable.tsx` should copy this
  pattern directly rather than reinvent it.
- `SectionHeader.tsx` / `SectionSkeleton.tsx` (from `macro/`) for
  loading/empty states.
- `RegimeCard.tsx`'s "current regime" banner pattern for the "Current
  regime (DB): X since Y" info line.

**New:**
- `BacktestTable.tsx` — ticker rows grouped by asset class, columns
  Occurrences/Avg High%/Avg Low%/Hit Rate/Edge/Avg Return%, same
  color-coding rules as `_edge_color`/`_bt_occ_pct_style` in `app.py`.
- `RegimeSelector.tsx` — Compass Q / Grid Q dropdowns, min-occurrences
  slider, group multiselect, lookback radio. No Streamlit sidebar
  equivalent exists in the Next.js app yet — this is genuinely new UI,
  not a port.
- `OccurrenceDetailTable.tsx` — expandable per-ticker occurrence list.

No charting library needed for this tab (plain tables) — DEEP DIVE's
heatmap would need Plotly.js, but that's out of scope here.

## 6. Compute concern — flagged as the central risk

Comparison:
- **Phase 1** (LIVE): single S3 `GetObject` of a pre-built Excel
  workbook. ~1.5s measured.
- **Phase 2** (MACRO): a handful of small FRED/BEA/BLS/yfinance calls
  per cache miss, seconds each, bounded by known small payloads.
- **Phase 3** (BACKTEST), if built the naive way (compute-on-miss like
  Phase 2): ~135 unbounded per-symbol DynamoDB Queries pulling full
  history (tens of thousands of items total) plus the pandas occurrence
  walk across all 16 combos. **This is a different order of magnitude
  and very likely exceeds a reasonable request timeout on Render free
  tier**, especially stacked on the already-measured ~75s cold start.

**This is why the plan separates `/refresh` (does the expensive work,
called out-of-band, no user waiting on it) from `/table` and
`/occurrences` (read the cache, always fast, comparable to Phase 1's
~1.5s once warm).** The open question this creates — Render free tier
has no built-in cron of its own — is called out below as a decision for
you, not resolved unilaterally here.

## 7. Dependencies to add

None on the backend (pandas already in `requirements.txt`). None on the
frontend (no new npm packages — plain tables, no charts).

## 8. Estimated LOC + effort

- Backend: `api/backtest_data.py` (~230 LOC: regime-period port ~50,
  occurrence/stats port ~90, refresh orchestration ~50, response
  shaping ~40) + `cache.py` TTL entry (~5) + `main.py` wiring (~20).
  ≈ **255 LOC**.
- Frontend: `BacktestTable.tsx` (~120), `RegimeSelector.tsx` (~80),
  `OccurrenceDetailTable.tsx` (~100), `web/app/backtest/page.tsx`
  wiring (~50), types (~30). ≈ **380 LOC**.
- **Total ≈ 635 LOC** — larger than Phase 2 MACRO, driven mostly by the
  refresh-endpoint split and the multi-control selector UI (Phase 2 had
  no user-adjustable filters at all).
- Effort: comparable build time to Phase 2 for the code itself; the
  refresh-trigger mechanism (open decision below) could add
  coordination overhead if it needs a new EventBridge rule or similar.

---

## Risks + open decisions (for your review, not decided here)

1. **Daily refresh trigger mechanism — needs your call.** Render free
   tier has no built-in scheduler. Options: (a) a new EventBridge rule
   pinging the `/refresh` endpoint once daily (small, but touches AWS
   infra for a Vercel-side concern — mild architectural mixing); (b) a
   scheduled GitHub Action; (c) lazy refresh-on-miss accepted as a rare,
   known-slow first-request-of-the-day path with a long client-side
   timeout and a loading state that says so explicitly. None of these
   are free of tradeoffs — flagging for your decision rather than
   picking one.
2. **DEEP DIVE/SCENARIO reuse** — both use the identical engine and
   data sources. Building the cache dataset to already cover all 16
   combos (which this plan does, since `/table` needs that anyway)
   means DEEP DIVE's 4×4 grid becomes nearly free to add later — a
   `deep_dive_grid`-equivalent read of the same cache, no new heavy
   compute. Not in scope now, just noting the design doesn't foreclose
   it.
3. **Lookback filtering interacts with cache granularity.** The cache
   stores full-history occurrences; lookback (5y/10y/All) filtering
   happens at read time by date-filtering the cached occurrence rows.
   This is cheap and correct as long as occurrence rows carry their
   `start_date` — confirmed they do (`get_occurrences` returns
   `start_date`/`end_date` per row).
4. **Proxy tickers** (`data_cache.BACKTEST_PROXIES`, currently empty in
   the source read but present as a mechanism) — if any proxy mappings
   get added on the Streamlit side later, the ported cache-build logic
   needs to apply the same `symbol → proxy` resolution `load_all_prices`
   does, or the two apps will silently diverge on which underlying
   price series a ticker's stats are built from.
5. **Cache staleness vs. regime-period changes are rare but
   high-stakes.** A regime change is infrequent (event-driven, not
   daily) but exactly the moment the BACKTEST numbers most need to be
   current. A 24h TTL means up to a day's lag after a regime flip before
   the new period is reflected — acceptable for a backtest/research tool
   (not a real-time signal), but worth confirming that's actually fine
   for how you intend to use this tab.
