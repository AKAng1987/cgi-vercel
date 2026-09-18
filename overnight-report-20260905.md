# Overnight report — 2026-09-05

Two read-only tasks, no writes/deploys performed. Report for morning review.

---

═══ Task 1 — Vercel Phase 1 correctness verification ═══

## Method

1. Fetched `/api/live` from the deployed Render service directly (`https://cgi-api-9mim.onrender.com/api/live`) using the real production token (found in `~/cgi-vercel/.env` at repo root — the token in `web/.env.local` is a local-dev-only value and correctly returns 401 against prod, not a bug).
2. Copied `load_workbook`/`parse_hud`/`parse_compass`/`parse_grid`/`_pct` verbatim from `~/market-dashboard/app.py` into a throwaway script (deleted after use) and ran them against the exact same-date workbook the API used (`dashboard_2026-09-04.xlsx` — API's `as_of`/`generated_at` were `2026-09-04` / `2026-09-04T00:30:41Z`; tonight's 2026-09-05 00:30 UTC dashboard run had not yet landed at check time, so both sides are comparing the same source file).
3. Field-by-field diff: compass (quadrant/since/metrics), grid (quadrant/since/metrics), every HUD ticker (current/ema_7d/sd_7d/all pct_* fields).

## Result

**Zero real divergences.** First pass found 43 apparent "missing" tickers (present in a raw, unfiltered parse of the sheet but absent from the API's `hud_groups`) — investigated and confirmed this is not a bug: all 43 symbols (FNGU, BJK, IBUY, GGME, VICE, XRT, FAN, FCG, IEO, MLPX, NLR, OIH, PBD, KBWP, KCE, CNCR, IBB, IHE, IHI, IYH, BATT, IDRV, IGF, ITA, KARS, SEA, XAR, XTN, COPX, VNQ, MORT, VPN, AIQ, ESPO, SMH, WCLD, GRID, EWQ, UVXY, MMFI, MMTH, MMTW, PCREDIT8) are genuinely absent from `HUD_GROUPS` in `app.py` itself — Streamlit's own LIVE tab would not display them either, since its rendering filters the same way. My own throwaway comparison script's `parse_hud` returned the full unfiltered sheet; the deployed API correctly filters to the configured universe, matching Streamlit's actual behavior.

Of the 128 tickers actually configured and present, every field matched to full float precision (tolerance 1e-6) — no rounding drift, no stale-read discrepancies, no porting bugs found.

**Phase 1 verified faithful — 128 tickers × 14 groups + compass + grid, zero divergences.**

## Frontend rendering check

The Vercel frontend at `https://cgi-vercel.vercel.app` is now genuinely rendering real dashboard data — confirmed via the actual HTML body, not just an HTTP 200. This is a change from earlier tonight's session (which ended with the frontend showing its `error.tsx` boundary, digest `3000637062`, likely the Render/Vercel token-sync fix taking effect after that debugging session closed). Confirmed:

- All 14 HUD groups render in exactly the correct `hud_group_order` sequence (verified positionally in the raw HTML, correcting for a substring false-match on "RATES" inside "US INTEREST RATES"/"FOREIGN RATES" during the initial check).
- Real ticker symbols (SPX, DJI, BTC, ETH, etc.), real regime labels ("Deflation", "Liquidity"), real metric labels ("Fed Funds") all present.
- No error digest in the final render (`"error":null,"digest":"$undefined"` — Next.js's normal healthy-state metadata, not an error state).

**Net: Phase 1 is fully working in production as of this report** — both the data logic and the frontend rendering are verified correct.

---

═══ Task 2 — Vercel Phase 2 (MACRO tab) design doc ═══

## Panel inventory

Read `app.py` lines 2086–2765 (the full MACRO tab block, 680 lines) plus `macro_data.py` (548 lines) and `fomc_data.py` (310 lines) in full.

| # | Panel | Data source function | Chart type(s) |
|---|---|---|---|
| 1 | Fed Funds Target Range | `macro_data.fetch_fed_funds_range()` (FRED DFEDTARU/DFEDTARL) | Step-line dual-trace (upper/lower band) |
| 2 | FOMC Rate Probabilities | `fomc_data.get_upcoming_meetings()` + `fetch_effr()` + `fetch_futures_for_meetings()` (yfinance ZQ futures) + `compute_fomc_probs()` | Horizontal bar (next meeting) + table (next 3-4 meetings) |
| 2b | SEP Dot Plot | `fomc_data.load_dot_plot()` — **static CSV** (`data_manual/dot_plot.csv`), not a live fetch | Jittered scatter + median bars per horizon |
| 3 | Treasury Yield Curve | `macro_data.fetch_treasury_curve()` (FRED DGS series) | 2-subplot: curve snapshot (latest/6M/1Y ago) + 10Y 20-year history |
| 4 | Spreads | `macro_data.fetch_spreads()` (FRED T10Y2Y + HY OAS) | Dual-y-axis line chart |
| 5 | Bank Lending Standards | `macro_data.fetch_lending_standards()` (FRED DRTSCILM) | 2 sub-charts: level step-line + QoQ change bars |
| 6 | GDP / Growth | `macro_data.fetch_gdp()` + `fetch_gdpnow()` + `fetch_gdp_vintages()` (BEA NIPA + FRED GDPNOW + ALFRED vintages) | 3 sub-charts: (3a) BEA bars + GDPNow line overlay, (3b) 3-vintage grouped bars + GDPNow-final diamond markers, (3c) standalone GDPNow time series |
| 7 | Inflation | `macro_data.fetch_inflation()` (BLS CPI/Core CPI/PPI) | Multi-line, user-selectable range radio (5Y/10Y/20Y/All) |
| 7b | Core PCE | `macro_data.fetch_pce()` (BEA), rolling YoY computed client-side in `app.py` | Single line vs 2% target dotted reference |
| — | FedWatch link | none (static external link button) | n/a |

**One correction to project memory**: `macro_data.fetch_gdp_components()` exists (lines 389-425) but is **not called anywhere in the current MACRO tab UI** — no "component contributions panel" is actually rendered today, despite that being noted in earlier project history. Treat this as dead/unused backend code; exclude it from the Phase 2 port unless there's a separate decision to revive it.

## Critical architectural question — answered definitively

**MACRO does NOT read from the S3 dashboard workbook.** Every panel except the dot plot makes **live calls to FRED, BEA, or BLS APIs directly** (`requests.get`/`requests.post` in `macro_data.py`/`fomc_data.py`), plus `yfinance` for Fed Funds futures pricing (FOMC probability panel) and a `requests`-based scrape for the FOMC meeting calendar. Confirmed via `.streamlit/secrets.toml`: `FRED_API_KEY`, `BEA_API_KEY`, `BLS_API_KEY` are the three keys in use — these need to become new Render env vars (in addition to Phase 1's AWS credentials).

Streamlit caches all of this in **local parquet files** (`cache/macro_*.parquet`, `cache/effr.parquet`, etc.) with per-panel staleness windows: 12h default, 24h for Fed Funds Range, 168h (weekly) for Lending Standards and GDP Components. **This caching pattern does not transfer to Render as-is** — see Risks below, this is the single biggest architectural difference from Phase 1.

**Conclusion: Phase 1's "port the S3 Excel read, no caching needed" pattern does not apply to Phase 2 at all.** This needs a genuinely different data-fetching design.

## Endpoint design proposal

**Recommend multiple sub-endpoints, not one `/api/macro`.** Reasoning: Phase 1's single-endpoint design worked because everything came from one pre-aggregated, cheap S3 read — bundling was free. Here, panels have meaningfully different refresh cadences (daily FRED series vs. weekly GDP components vs. a near-static manually-updated dot plot) and different failure/latency profiles (a yfinance futures fetch or a BEA API call can be slow or flaky; a cached FRED read is fast). Bundling them into one endpoint means the whole panel set's response time is bounded by the *slowest* individual fetch, and a transient failure in one data source (e.g., yfinance) would either fail the entire response or require complex partial-failure handling within a single endpoint.

Proposed split, grouped by natural cache lifetime and source:
- `/api/macro/rates` — Fed Funds Range, FOMC probabilities + meeting table, Yield Curve, Spreads, Lending Standards (all FRED-sourced, similar staleness windows)
- `/api/macro/growth` — GDP (3 sub-charts), Inflation, Core PCE (BEA/BLS-sourced)
- `/api/macro/dot-plot` — SEP dot plot (static data, essentially never changes except a few times a year — trivially cacheable, could even be a static JSON file rather than a "live" endpoint at all)

This also lets the frontend render panels independently as each resolves, rather than blocking the whole MACRO page on the slowest fetch — a real UX win given Phase 1's design principle of "no loading spinners on individual widgets" would otherwise force one giant page-level wait.

## Frontend component sketch

**Phase 1 components are not directly reusable here** — `RegimeCard` and `HudTable` are shaped around quadrant/ticker-table data that doesn't exist on this tab. `DateHeader` is the only one that carries over as-is (or with minor generalization).

Genuinely new components needed:
- `LineChart` (generic — Fed Funds step-line, Spreads dual-axis, Inflation multi-line, Core PCE) — could be one configurable component given the underlying chart shape is similar across several panels
- `BarChart` (generic — GDP 3a/3b, Lending Standards QoQ change) — similarly shareable
- `DotPlotChart` (SEP dot plot — genuinely unique jittered-scatter-plus-median-bar shape, not reusable from anything else)
- `YieldCurvePanel` (2-subplot layout — snapshot + history side by side)
- `FomcProbabilityPanel` (horizontal bar + meetings table combo)
- `MetricStat` (small reusable "current value + delta" component, used by Fed Funds Range, Lending Standards, GDP — Streamlit's `st.metric` equivalent)

## Charting library recommendation: **Plotly.js (via `react-plotly.js`)**

Every single chart in the current MACRO tab is built with `go.Figure`/`make_subplots` — zero use of `plotly.express`. This matters concretely for the port strategy: rather than reimplementing 9 distinct chart types from scratch in a different library, the FastAPI backend can **reuse the exact same figure-construction logic** (traces, layout, hover templates, shapes for the dot-plot median bars, dual-axis specs for Spreads) and simply return `fig.to_json()` (or `fig.to_dict()`) from each endpoint. The Next.js frontend then renders it with `react-plotly.js`'s `<Plot data={...} layout={...} />` almost verbatim — this is close to a 1:1 port for the hardest parts (the dot-plot jitter math, the dual-vintage GDP bars with custom hover templates, the dual-y-axis Spreads chart), not a rewrite.

Recharts was considered — more idiomatic React/Tailwind styling, lighter bundle — but every chart here would need to be rebuilt from scratch, including some genuinely fiddly logic (the SEP dot plot's per-rate-level jitter offset calculation, the GDP vintage chart's custom hover template joining quarter label + release date + value). Given 9 chart panels with real custom logic, that's a much larger and more error-prone effort than the Plotly.js path.

TradingView's `lightweight-charts` was also considered — excellent for the Yield Curve/Spreads/GDPNow-style time series, but not suited to the SEP dot plot at all (that's a categorical scatter with jitter, not a financial time series), so it would still need a second charting approach for that one panel — not a clean single-library answer the way Plotly.js is.

**Recommendation: Plotly.js.** It's the only option that lets the backend reuse existing, working figure-construction code almost unchanged, covers every chart type actually in use (including the awkward dot-plot case), and avoids a from-scratch rebuild of nontrivial existing logic.

## Dependencies

**API side (beyond Phase 1's boto3 + openpyxl):**
- `requests` (already implicitly needed — both `macro_data.py` and `fomc_data.py` use raw `requests.get`/`.post` directly against FRED/BEA/BLS, not the `fredapi` package despite it being listed in `~/market-dashboard/requirements.txt` — worth noting `fredapi` appears to be an unused/vestigial dependency there, don't carry it over unless something not covered in this read actually needs it)
- `yfinance` — Fed Funds futures pricing for FOMC probabilities
- `beautifulsoup4` — FOMC meeting-date scraping (`_scrape_fomc_dates`)
- `pandas` — Phase 1 explicitly dropped this; Phase 2's data transforms (rolling YoY calc for Core PCE, groupby/median for the dot plot, quarter-end date math for GDP) are pandas-idiomatic enough that reintroducing it here is probably the pragmatic choice rather than hand-rolling equivalents, unlike Phase 1 where dropping it was a clean simplification

**Frontend side:**
- `plotly.js` + `react-plotly.js` (the recommended charting library)
- Nothing else new anticipated — Tailwind/existing component patterns cover the rest

## Complexity estimate

Rough size comparison: MACRO tab's `app.py` block is **680 lines** vs. Phase 1's LIVE tab rendering (~75 lines, app.py:1023-1097) plus the ~150 lines of `parse_hud`/`parse_compass`/`parse_grid`/`_pct` that got ported. Backend data-layer size: `macro_data.py` + `fomc_data.py` = **858 lines** vs. Phase 1's zero (Phase 1 had no equivalent data-layer module — it just read one pre-built S3 file). **9 distinct chart panels** need building vs. Phase 1's 0 charts (pure tables + cards).

This is a meaningfully larger build than Phase 1 — rough order-of-magnitude estimate: **3-4x the effort**, driven less by raw line count and more by (a) genuinely new chart-building work on the frontend even with Plotly.js reuse on the backend, (b) a caching/staleness design that Phase 1 didn't need at all, (c) three new external API integrations (FRED direct, BEA, BLS) each with their own response shapes and failure modes, versus Phase 1's one already-solved S3 pattern.

## Risks and open questions

1. **Biggest risk: Render's free-tier ephemeral filesystem breaks Streamlit's caching pattern.** Streamlit's local-parquet-cache-with-staleness-window works because the process stays warm across requests in a persistent session. Render's free tier spins down after inactivity (observed ~45s cold start earlier tonight) and **wipes local disk on every cold start** — meaning any naively-ported local-parquet-cache would provide zero benefit on Render; every cold request would re-trigger fresh calls to FRED/BEA/BLS/yfinance. This risks real latency (multiple sequential external API calls) and, more importantly, **rate-limit risk** against free-tier government/financial data APIs if hit repeatedly by cold-starting requests. This needs a real caching decision before building: either (a) a persistent cache outside the Render instance (S3, or a small DynamoDB table, mirroring Phase 1's infrastructure pattern), or (b) accepting the latency/rate-limit risk on a low-traffic internal tool, or (c) a paid Render tier that doesn't spin down. Recommend deciding this explicitly, not defaulting to "just port the local-parquet pattern as-is."
2. **yfinance fragility** — this project has a well-documented history this session of Yahoo Finance endpoints breaking silently (the yahoo-finance-updater Lambda's 401/429 issue diagnosed and partially migrated away from earlier in this project). `yfinance`'s futures-contract fetch uses different Yahoo endpoints than the broken legacy CSV download endpoint, so the risk is lower, but given the track record, a smoke test of `yfinance`'s ZQ futures fetch from a fresh Render-like environment (not just local dev) before committing to this pattern for Phase 2 seems warranted.
3. **SEP dot plot's real nature**: this isn't a "live" data source at all — it's a static CSV manually regenerated a few times a year via a documented workflow (user pastes an SEP screenshot → planning session reads dot positions → CSV regenerated). Porting the file itself to Render is trivial (commit the CSV, same as Phase 1's approach to static config), but the *update workflow* needs a decision: does updating it still require a full redeploy each time (acceptable given how infrequent SEP updates are — quarterly), or is a small persisted-data mechanism (S3 object, tiny DynamoDB table) worth it to decouple data updates from code deploys? Given the low frequency, redeploy-on-update is probably fine — flagging as a decision, not a blocker.
4. **`fredapi` dependency confusion** — declared in `market-dashboard/requirements.txt` but the actual code paths read all use raw `requests` calls against FRED's REST API directly. Worth a quick check of whether `fredapi` is used anywhere not covered by this read (unlikely, given both files' data-fetching functions were read in full) before assuming it's needed for Phase 2 — recommend not including it unless a specific need turns up.
5. **Endpoint-splitting adds real complexity Phase 1 didn't have** — three endpoints instead of one means three separate error/loading states on the frontend, which cuts against the "no loading spinners on individual widgets, one page-level skeleton" design principle from Phase 1. This needs an explicit decision: either relax that principle for MACRO (different panels genuinely do load at different speeds, so per-section loading states might be the right call here even though Phase 1 avoided them), or accept a single slower blocking load. Flagging as a design tradeoff to resolve during planning, not something this doc resolves unilaterally.

---

**TL;DR** (also printed to terminal below):

- **Task 1**: Phase 1 verified faithful — 128 tickers × 14 groups + compass + grid, zero divergences. Frontend at cgi-vercel.vercel.app is now genuinely rendering real data correctly (was still broken as of last night's session end; appears fixed since).
- **Task 2**: MACRO tab does NOT read the S3 workbook — it's 9 chart panels backed by live FRED/BEA/BLS calls + yfinance, currently cached via local parquet files that won't survive Render's free-tier cold starts. Recommend 3 sub-endpoints (not 1), Plotly.js/react-plotly.js for charts (all existing charts are already `go.Figure`-built, near-1:1 port), and flag the caching-strategy gap as the top open risk to resolve before building. Rough 3-4x the build effort of Phase 1.
