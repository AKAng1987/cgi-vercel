# Vercel Phase 1 build — LIVE tab as first real endpoint

Full spec from Claude.ai. Saved verbatim for session continuity.

## 1. Endpoint design

One endpoint, one round-trip. Everything the LIVE tab needs in a single
response — no waterfall calls, no client-side data joins.

    GET /api/live
    Authorization: Bearer <API_TOKEN>

Optional query param: ?date=YYYY-MM-DD (defaults to latest available).

## 2. Response schema

```json
{
  "as_of": "2026-09-04",
  "generated_at": "2026-09-04T00:35:12Z",
  "compass": {
    "quadrant": 3,
    "label": "C3 — Liquidity↓ Credit↑",
    "since": "2026-05-14",
    "stale_note": null,
    "metrics": {
      "fed_funds": 4.25,
      "sofr": 4.30,
      "bank_lending_pct_yoy": 8.2
    }
  },
  "grid": {
    "quadrant": 2,
    "label": "G2 — Reflation",
    "since": "2026-04-01",
    "metrics": {
      "gdp_growth_yoy": 2.1,
      "cpi_yoy": 3.4,
      "core_pce_yoy": 2.8
    }
  },
  "hud_groups": [
    {
      "name": "US EQUITIES",
      "default_rs_denom": "SPX",
      "tickers": [
        {
          "symbol": "SPX",
          "current": 7631.47,
          "ema_7d": 7679.36,
          "sd_7d": 0.436,
          "pct_1d": 0.52,
          "pct_5d": 1.23,
          "pct_1m": 3.14,
          "pct_3m": 8.51,
          "pct_1y": 22.04,
          "as_of": "2026-09-04",
          "stale_days": 0
        }
      ]
    }
  ],
  "hud_group_order": [
    "US EQUITIES", "INDEX ETF", "SECTOR ETF", "US INTEREST RATES",
    "BONDS ETF", "SPREADS", "RATES", "COMMODITIES METALS",
    "COMMODITIES CONT.", "AGRICULTURAL", "COUNTRY ETF",
    "FOREIGN RATES", "FX"
  ]
}
```

## 3. Server implementation (FastAPI on Render)

Add new route to api/main.py. Reads DynamoDB directly using boto3 (same
tables/clients that ~/market-dashboard/data_cache.py already uses — port
the read patterns, don't reinvent). No caching layer needed for Phase 1.

Per section:
- compass/grid: query cmon-stage-backend-model-history with PK
  "compass_US" / "grid_US", sort by SK metrics_date desc, take latest.
  Compute since-date by walking backward until quadrant changes.
  Defensive fallback if quadrant is None (matches the Streamlit app's
  fallback that reads cache/model_compass_US.parquet).
- hud_groups: iterate HUD_GROUPS from ~/market-dashboard/app.py (lines
  ~51-115, port the OrderedDict structure as-is). For each ticker:
  fetch latest cmon-stage-backend-derived_metrics row (ema_7d, sd_7d,
  percent_diff_1d/5d/7d/1m/3m/6m/1y) plus current close from
  cmon-stage-backend-price-history. Compute stale_days = today - latest
  price-history date (surfaces FRED FX stall + any future staleness to
  the UI).
- hud_group_order: static list, matches HUD_GROUPS.keys() order from
  app.py.

Environment vars needed on Render:
- AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION=ap-southeast-1
- Existing API_TOKEN (bearer auth already established)

## 4. Frontend component (Next.js Server Component)

Replace the green status card at web/app/page.tsx with the LIVE dashboard.

Three visual sections stacked:

```tsx
async function LivePage() {
  const data = await fetchLive();  // uses existing lib/api.ts pattern
  return (
    <main>
      <DateHeader asOf={data.as_of} generatedAt={data.generated_at} />
      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <RegimeCard
          kind="compass"
          quadrant={data.compass.quadrant}
          label={data.compass.label}
          since={data.compass.since}
          staleNote={data.compass.stale_note}
          metrics={data.compass.metrics}
        />
        <RegimeCard
          kind="grid"
          quadrant={data.grid.quadrant}
          label={data.grid.label}
          since={data.grid.since}
          metrics={data.grid.metrics}
        />
      </section>
      {data.hud_group_order.map(name => {
        const group = data.hud_groups.find(g => g.name === name);
        return group ? <HudTable key={name} group={group} /> : null;
      })}
      <TradingViewChart symbol={selectedSymbol} />
    </main>
  );
}
```

Components:
- RegimeCard: color-coded by quadrant (match Streamlit's palette in app.py
  CLOCK_Q_COLOR), shows label + since-date + metric list. Stale-note shows
  as yellow warning banner if present.
- HudTable: columns Symbol · Current · EMA-7D · SD-7D · %1D · %5D · %1M ·
  %3M · %1Y. Positive % green, negative % red (Tailwind palette). Row
  clickable → sets selectedSymbol state in parent client wrapper, updates
  TradingView chart.
- TradingViewChart: client component (useState), embeds TradingView widget
  script — port from Streamlit's tradingview_widget() function to JSX.

Loading state: Next.js loading.tsx skeleton. Error boundary: error.tsx
with retry.

## 5. Design principles

- Match the visual density of the Streamlit LIVE tab — this is a working
  trader's dashboard, not marketing copy
- Dark theme by default (matches current CGI aesthetic)
- Mobile-responsive but desktop-first (real use case is desktop)
- No loading spinners on individual widgets — one page-level skeleton

## 6. Deploy discipline

- Push to main → Render auto-deploys API, Vercel auto-deploys frontend
- Verify both environments' env vars are set before pushing
- Test locally first: `uvicorn main:app --reload` on Render side,
  `pnpm dev` (or `npm run dev`) on Vercel side

## 7. Explicitly out of scope for Phase 1

- Any Markov / regime signal work (that's Phase 2)
- New features not in current Streamlit LIVE tab (this is a port, not an
  enhancement)
- Streamlit deprecation (both stay live in parallel until Vercel is
  proven trusted)
- MACRO/BACKTEST/DEEP DIVE/SCENARIO/RRG/CLOCK tabs (later phases)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REVISED ARCHITECTURE (approved deviations from the spec above)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Investigation before building found that `app.py` does NOT read
`derived_metrics`/`price-history` per-symbol for the LIVE tab at all —
`derived_metrics` has zero references anywhere in the file. The entire
LIVE tab (HUD table, COMPASS, GRID) is sourced from ONE S3 Excel file,
written nightly at 00:30 UTC by the separate `dashboard` Lambda:

- Bucket: `cmon-stage-backend-369568916817-ap-southeast-1-reports`
- Key pattern: `Dashboard/dashboard_{YYYY-MM-DD}.xlsx`
- `list_dashboard_dates()` (app.py:213) lists matching S3 objects, sorted
  descending — this is "?date=YYYY-MM-DD, defaults to latest."
- `load_workbook(date_str)` (app.py:230) — `s3.get_object` + `openpyxl.load_workbook(..., data_only=True)`.
- `parse_hud(ws)` (app.py:247), `parse_compass(ws)` (app.py:288),
  `parse_grid(ws)` (app.py:324), `_pct(current, ref)` (app.py:238) —
  parse the HUD/COMPASS/GRID sheets (sheet_names[0/1/2]) into records.
  Compass/grid "since" date is a string ALREADY embedded in the sheet
  ("Quadrant N since YYYY-MM-DD"), extracted via regex — not computed
  from model-history by walking backward.

**Approved decision: `/api/live` ports this S3 Excel read+parse path,
not the spec's original raw-DynamoDB-fan-out design.** Reasons: (1)
avoids reimplementing the since-date "walk backward until quadrant
changes" logic from scratch, which already exists and is already
correct — a reimplementation disagreeing with Streamlit during the
parallel-running trust-building period would be the worst failure mode;
(2) one S3 GetObject + parse vs. ~150+ tickers × 2 DynamoDB queries each
with no caching layer; (3) the spec's own example `generated_at`
timestamp (00:35:12Z) already implies "S3 object's last-modified," not
"API request time."

Six approved deviations from the original spec:
1. Data source for compass/grid/hud_groups: S3 Excel port (above).
2. `hud_group_order`: include `"CRYPTO"` (BTC/ETH/BITO) — the spec's
   list of 13 omitted it; `app.py`'s actual `HUD_GROUPS` (app.py:51-120)
   has 14 groups including CRYPTO last. Include it.
3. Fallback when `quadrant is None`: query `cmon-stage-backend-model-history`
   directly (PK `compass_US`/`grid_US`, latest row) rather than a local
   parquet cache — FastAPI/Render is stateless per-request, unlike the
   long-running Streamlit session the original fallback assumes.
4. Drop `pandas` from the ported parsing logic — rewrite `parse_hud`/
   `parse_compass`/`parse_grid` to return plain dicts/lists, not
   DataFrames. Smaller Render dependency footprint, no behavior change.
5. Package manager: no lockfile exists yet in `web/`; use `npm`
   (matches README's documented flow), not `pnpm`.
6. Open question, to resolve during the build by inspecting a real
   workbook: does the HUD sheet carry a per-row/per-ticker date, or only
   a sheet-level "as of" date? The spec wants per-ticker `as_of`/
   `stale_days`; `parse_hud` as it exists today doesn't extract a
   per-row date. If the sheet doesn't carry one, extend `parse_hud` to
   derive `stale_days` from workbook-level as-of date minus per-ticker
   latest-available date; if that's not viable, drop `stale_days` from
   the response for Phase 1 and flag as follow-up.

IAM: new least-privilege user `cgi-vercel-render-svc` (programmatic
access only) — `s3:GetObject`+`s3:ListBucket` scoped to
`cmon-stage-backend-369568916817-ap-southeast-1-reports`/`Dashboard/*`,
plus `dynamodb:Query` on `cmon-stage-backend-model-history` only (the
fallback path). Not the `arvin` user — that's for interactive/session
work only, never for a deployed service's credentials.

Explicit constraint for this build: zero AWS write operations expected.
Do not touch derived-metrics-updater alias, price-updater alias, or any
other production Lambda infra while building Phase 1 — this work is
pure read-only against S3 + one DynamoDB table's read path.
