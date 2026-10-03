"""
series_write.py -- Append-only loader for the few series that have no free
API and are pulled from TradingView by a monthly cloud routine:
ISM prices/PMI/activity, Challenger job cuts, Baltic Dry.

POST /api/series/{symbol}  body {"rows": [{"date": "YYYY-MM-DD", "value": 71.1}, ...]}

Guards (this endpoint is reachable without the bearer token because the
routine's environment cannot hold secrets):
  - symbol must be in ALLOWED; source/frequency are fixed per symbol
  - values must be finite and inside the symbol's plausible range
  - dates must be ISO, not in the future, and strictly after the last
    stored row -- existing rows are never overwritten
  - at most 24 rows per call
Worst case for abuse is a few bogus recent rows on one whitelisted symbol,
which the audit CSVs in market-dashboard/data_manual can restore.
"""
from __future__ import annotations

import datetime as dt
import math
from decimal import Decimal

import boto3
from fastapi import HTTPException

REGION = "ap-southeast-1"
PRICE_TABLE = "cmon-stage-backend-price-history"
MAX_ROWS = 24

# symbol -> (source, frequency, min, max, TradingView symbol for the routine)
ALLOWED = {
    "ISM_MFG_PRICES":   ("tradingview", "1M", 0.0, 100.0, "ECONOMICS:USMPR"),
    "ISM_SVC_PRICES":   ("tradingview", "1M", 0.0, 100.0, "ECONOMICS:USNMPR"),
    "ISM_MFG_PMI":      ("tradingview", "1M", 0.0, 100.0, "ECONOMICS:USBCOI"),
    "ISM_SVC_ACTIVITY": ("tradingview", "1M", 0.0, 100.0, "ECONOMICS:USNMBA"),
    "CHALLENGER":       ("challenger_gray", "1M", 0.0, 2_000_000.0, "ECONOMICS:USJC"),
    "BDI":              ("tradingview", "1W", 0.0, 20_000.0, "INDEX:BDI"),

    # ── breadth (daily) ──────────────────────────────────────────────────
    # These were registered in metrics-source under source=tradingview but
    # were NOT here, and no Lambda serves tradingview. So they fell between
    # two lists: registered enough to look automated, absent from the manual
    # worklist that /api/freshness builds from ALLOWED. Nothing refreshed
    # them and nothing reported that.
    #
    # Found 2026-09-28 because the LIVE breadth panel stopped moving: it read
    # net -54 from 2026-09-23 while the source had -47 for 09-25. The panel
    # was computing correctly from data two trading days old.
    #
    # Daily, and they feed the primary risk read, so they go stale faster and
    # more visibly than anything else on this list.
    "HIGQ":             ("tradingview", "1D", 0.0, 10_000.0, "INDEX:HIGQ"),
    "LOWQ":             ("tradingview", "1D", 0.0, 10_000.0, "INDEX:LOWQ"),
    "HIGN":             ("tradingview", "1D", 0.0, 10_000.0, "INDEX:HIGN"),
    "LOWN":             ("tradingview", "1D", 0.0, 10_000.0, "INDEX:LOWN"),
    "NCFD":             ("tradingview", "1D", 0.0, 100.0, "INDEX:NCFD"),
    "NCTH":             ("tradingview", "1D", 0.0, 100.0, "INDEX:NCTH"),
    "MMFD":             ("tradingview", "1D", 0.0, 100.0, "INDEX:MMFD"),
    "MMTW":             ("tradingview", "1D", 0.0, 100.0, "INDEX:MMTW"),
    "MMFI":             ("tradingview", "1D", 0.0, 100.0, "INDEX:MMFI"),
    "MMTH":             ("tradingview", "1D", 0.0, 100.0, "INDEX:MMTH"),

    # ── Country macro, added 2026-09-26 for the COUNTRIES tab ──────────────
    # Policy rates. SIX countries, not seven: the US is deliberately absent.
    # It is already served by DFEDTARU (policy rate), CPIAUCSL (inflation) and
    # GDP, which are the canonical series the Compass/Grid models themselves
    # read. Adding US_POLICY_RATE alongside DFEDTARU would create two US rate
    # series with no rule about which wins -- the same shape as the bundled
    # HUD_GROUPS copy that drifted 38 tickers, and as GOLD sitting outside the
    # commodities map. One source per fact.
    #
    # All six tested and resolving. The inflation and GDP
    # entries below are listed from the catalog and are verified by the
    # onboarding script before their first write -- anything that fails moves
    # into UNRESOLVED rather than sitting here looking real.
    #
    # Bounds are per-series and deliberately wide on the low side: JPINTR has
    # traded at -0.1 and EUINTR at 0.0, so a 0.0 floor would silently reject
    # exactly the observations that matter most.
    "PH_POLICY_RATE":   ("tradingview", "1M", -5.0, 100.0, "ECONOMICS:PHINTR"),
    "CN_POLICY_RATE":   ("tradingview", "1M", -5.0, 100.0, "ECONOMICS:CNINTR"),
    "JP_POLICY_RATE":   ("tradingview", "1M", -5.0, 100.0, "ECONOMICS:JPINTR"),
    "KR_POLICY_RATE":   ("tradingview", "1M", -5.0, 100.0, "ECONOMICS:KRINTR"),
    "GB_POLICY_RATE":   ("tradingview", "1M", -5.0, 100.0, "ECONOMICS:GBINTR"),
    "EU_POLICY_RATE":   ("tradingview", "1M", -5.0, 100.0, "ECONOMICS:EUINTR"),

    # Inflation and GDP, both already YoY at source.
    "PH_CPI_YOY":       ("tradingview", "1M", -25.0, 100.0, "ECONOMICS:PHIRYY"),
    "CN_CPI_YOY":       ("tradingview", "1M", -25.0, 100.0, "ECONOMICS:CNIRYY"),
    "JP_CPI_YOY":       ("tradingview", "1M", -25.0, 100.0, "ECONOMICS:JPIRYY"),
    "KR_CPI_YOY":       ("tradingview", "1M", -25.0, 100.0, "ECONOMICS:KRIRYY"),
    "GB_CPI_YOY":       ("tradingview", "1M", -25.0, 100.0, "ECONOMICS:GBIRYY"),
    "EU_CPI_YOY":       ("tradingview", "1M", -25.0, 100.0, "ECONOMICS:EUIRYY"),

    "PH_GDP_YOY":       ("tradingview", "1Q", -50.0, 50.0, "ECONOMICS:PHGDPYY"),
    "CN_GDP_YOY":       ("tradingview", "1Q", -50.0, 50.0, "ECONOMICS:CNGDPYY"),
    "JP_GDP_YOY":       ("tradingview", "1Q", -50.0, 50.0, "ECONOMICS:JPGDPYY"),
    "KR_GDP_YOY":       ("tradingview", "1Q", -50.0, 50.0, "ECONOMICS:KRGDPYY"),
    "GB_GDP_YOY":       ("tradingview", "1Q", -50.0, 50.0, "ECONOMICS:GBGDPYY"),
    "EU_GDP_YOY":       ("tradingview", "1Q", -50.0, 50.0, "ECONOMICS:EUGDPYY"),

    # Loan growth. Two different measures, and which one a country gets is
    # decided by what actually resolves, not by preference:
    #
    #   {c}LG  -- Loan Growth YoY, already YoY at source. Resolves for CN, JP,
    #             EU ONLY. CNLG is +4.9%, matching the published China figure.
    #   {c}LPS -- Loans to Private Sector, a LEVEL in local currency and a
    #             NARROWER aggregate. YoY of CNLPS is -1.55% against CNLG's
    #             +4.9% -- these are not substitutes, and the page must say
    #             which one it is showing.
    #
    # US is served by BUSLOANS, already in price-history for the credit axis.
    "CN_LOAN_GROWTH_YOY": ("tradingview", "1M", -50.0, 100.0, "ECONOMICS:CNLG"),
    "JP_LOAN_GROWTH_YOY": ("tradingview", "1M", -50.0, 100.0, "ECONOMICS:JPLG"),
    "EU_LOAN_GROWTH_YOY": ("tradingview", "1M", -50.0, 100.0, "ECONOMICS:EULG"),

    # No LG series exists for these -- levels only, YoY derived at read time.
    # Bounds are wide because these are local-currency levels: KRLPS is
    # ~1.5 quadrillion won, GBLPS ~3.0 trillion pounds.
    #
    # FREQUENCY IS NOT UNIFORM and the YoY lag must follow it. PH and KR
    # publish monthly (12-bar lag); GB publishes QUARTERLY (4-bar lag).
    # Verified by bar spacing, not assumed: GBLPS bars are 90-92 days apart.
    # Reading GB with a 12-bar lag gives +11.19% where the truth is +7.34% --
    # a 3.85pp error that looks entirely plausible on a page.
    "PH_LOANS_PRIVATE": ("tradingview", "1M", 0.0, 1e18, "ECONOMICS:PHLPS"),
    "KR_LOANS_PRIVATE": ("tradingview", "1M", 0.0, 1e18, "ECONOMICS:KRLPS"),
    "GB_LOANS_PRIVATE": ("tradingview", "1Q", 0.0, 1e18, "ECONOMICS:GBLPS"),

    # Philippine curve. Named to the existing US03MY/US02Y/US10Y convention so
    # these land in the FOREIGN RATES group, which has declared PH10Y since
    # before any data existed for it.
    #
    # THESE HAVE NO LAMBDA. FRED maintains the US curve nightly with no Claude
    # in the path; TVC: symbols need the TradingView routine, which is the
    # fragile leg. country_data._curve() reports age_days per tenor so a stale
    # yield is visible rather than silently last-good -- the GOLD failure was
    # exactly a series nothing maintained and nobody checked.
    "PH03MY": ("tradingview", "1W", 0.0, 40.0, "TVC:PH03MY"),
    "PH01Y":  ("tradingview", "1W", 0.0, 40.0, "TVC:PH01Y"),

    # ── Per-country liquidity (Howell's two halves) ───────────────────────
    # The credit half ({c}LG / {c}LPS) is already above. These are the money
    # and central-bank halves. Still a PROXY, not Howell's index: no collateral
    # multiplier, no repo or dealer data, no cross-border weighting.
    #
    # Levels in LOCAL currency, so bounds are wide -- CNM2 is ~357 quadrillion
    # in yuan terms. Mislabelling the currency is the BOJ error, which put a
    # balance sheet out by 1000x and still looked entirely plausible.
    #
    # FRESHNESS VARIES AND IS NOT ASSUMED: PHM2 is current to 2026-07 while
    # PHCBBS lags to 2026-02. country_data reports age_days per series and
    # cache.is_stale() judges each against its own cadence.
    "PH_M2":        ("tradingview", "1M", 0.0, 1e18, "ECONOMICS:PHM2"),
    "CN_M2":        ("tradingview", "1M", 0.0, 1e18, "ECONOMICS:CNM2"),
    "JP_M2":        ("tradingview", "1M", 0.0, 1e18, "ECONOMICS:JPM2"),
    "KR_M2":        ("tradingview", "1M", 0.0, 1e18, "ECONOMICS:KRM2"),
    "GB_M2":        ("tradingview", "1M", 0.0, 1e18, "ECONOMICS:GBM2"),
    "EU_M2":        ("tradingview", "1M", 0.0, 1e18, "ECONOMICS:EUM2"),

    "PH_CB_ASSETS": ("tradingview", "1M", 0.0, 1e18, "ECONOMICS:PHCBBS"),
    "CN_CB_ASSETS": ("tradingview", "1M", 0.0, 1e18, "ECONOMICS:CNCBBS"),
    "KR_CB_ASSETS": ("tradingview", "1M", 0.0, 1e18, "ECONOMICS:KRCBBS"),
    "GB_CB_ASSETS": ("tradingview", "1M", 0.0, 1e18, "ECONOMICS:GBCBBS"),
    # JP_CB_ASSETS and EU_CB_ASSETS are NOT here any more: FRED carries the same
    # series (JPNASSETS x1e8, ECBASSETSW x1e6, equal on every shared date) and
    # the nightly fred-data-updater maintains them with no tokens. The stored
    # rows under the old names are kept as a fallback; see
    # country_data.FRED_SCALED.

    "PH02Y":  ("tradingview", "1W", 0.0, 40.0, "TVC:PH02Y"),
    "PH10Y":  ("tradingview", "1W", 0.0, 40.0, "TVC:PH10Y"),
}

# Symbols tested against TradingView and found NOT to resolve. Recorded so the
# next person does not spend the call finding out again.
UNRESOLVED = {
    # All four are listed in the economic-symbols catalog and all four return
    # "invalid symbol". The catalog is a cross-product of indicator x country
    # and does not check existence, so a listing is not evidence.
    "ECONOMICS:PHLG": "invalid symbol -- use PHLPS (level) and derive YoY",
    "ECONOMICS:USLG": "invalid symbol -- US loan growth comes from BUSLOANS",
    "ECONOMICS:KRLG": "invalid symbol -- use KRLPS (level) and derive YoY",
    "ECONOMICS:GBLG": "invalid symbol -- use GBLPS (level) and derive YoY",
}

_ddb = boto3.client("dynamodb", region_name=REGION)


def _last_date(symbol: str) -> str | None:
    page = _ddb.query(
        TableName=PRICE_TABLE,
        KeyConditionExpression="#s = :s",
        ExpressionAttributeNames={"#s": "symbol", "#d": "date"},
        ExpressionAttributeValues={":s": {"S": symbol}},
        ProjectionExpression="#d",
        ScanIndexForward=False,
        Limit=1,
    )
    items = page.get("Items", [])
    return items[0]["date"]["S"] if items else None


def describe() -> dict:
    """What the routine should pull: symbol, TradingView source, last stored date."""
    out = []
    for sym, (src, freq, lo, hi, tv) in ALLOWED.items():
        out.append({"symbol": sym, "tradingview": tv, "frequency": freq, "source": src,
                    "last_date": _last_date(sym), "min": lo, "max": hi})
    return {"as_of": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"), "series": out, "max_rows_per_call": MAX_ROWS}


# Cached payloads that read these symbols out of price-history.
#
# Writing a bar is not the same event as the page showing it. On 2026-09-28
# the breadth symbols were topped up to 09-25, the numbers were correct in
# DynamoDB, and LIVE still showed 09-23 -- `technicals` had been cached at
# 07:02 under a 12h TTL and would not rebuild until the evening. The data
# was fixed and the dashboard was still wrong, which from the outside is
# indistinguishable from the data not being fixed.
#
# So a write invalidates what depends on it. Doing it HERE rather than in
# the refresh routine means every writer gets it -- the routine, a manual
# backfill, anyone -- instead of it being a step someone has to remember.
_BREADTH = {"HIGQ", "LOWQ", "HIGN", "LOWN", "NCFD", "NCTH",
            "MMFD", "MMTW", "MMFI", "MMTH"}
_COUNTRY_PREFIXES = ("PH_", "CN_", "JP_", "KR_", "GB_", "EU_")


def _dependent_cache_keys(symbol: str) -> list[str]:
    keys: list[str] = []
    if symbol in _BREADTH:
        keys += ["technicals", "brief_daily", "brief_weekly"]
    if symbol.startswith(_COUNTRY_PREFIXES) or symbol.startswith("PH0") or symbol.startswith("PH1"):
        keys += ["countries", "liquidity"]
    if symbol.startswith("ISM_") or symbol == "CHALLENGER":
        keys += ["axis_drivers", "brief_daily"]
    return sorted(set(keys))


def _invalidate(symbol: str) -> list[str]:
    """Drop the cached payloads that read this symbol.

    Best-effort: a failure here must not fail the write. The bar is already
    in price-history and the cache expires on its own regardless, so the
    worst case is the old behaviour rather than a lost write."""
    import cache as _cache

    dropped: list[str] = []
    for key in _dependent_cache_keys(symbol):
        try:
            dropped += _cache.invalidate(key)
        except Exception:  # noqa: BLE001 -- see docstring
            _logger.exception("[series] could not invalidate %r", key)
    return dropped


def append(symbol: str, rows: list[dict]) -> dict:
    if symbol not in ALLOWED:
        raise HTTPException(status_code=404, detail=f"unknown series {symbol}")
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=400, detail="rows must be a non-empty list")
    if len(rows) > MAX_ROWS:
        raise HTTPException(status_code=400, detail=f"at most {MAX_ROWS} rows per call")
    src, freq, lo, hi, _ = ALLOWED[symbol]
    today = dt.datetime.now(dt.timezone.utc).date()
    last = _last_date(symbol)

    clean: list[tuple[str, float]] = []
    for r in rows:
        try:
            d = dt.date.fromisoformat(str(r["date"]))
            v = float(r["value"])
        except Exception:
            raise HTTPException(status_code=400, detail=f"bad row {r!r}")
        if not math.isfinite(v) or not (lo <= v <= hi):
            raise HTTPException(status_code=400, detail=f"{symbol} value {v} outside [{lo}, {hi}] on {d}")
        if d > today:
            raise HTTPException(status_code=400, detail=f"{d} is in the future")
        clean.append((d.isoformat(), v))
    clean.sort()
    if len({d for d, _ in clean}) != len(clean):
        raise HTTPException(status_code=400, detail="duplicate dates in rows")

    skipped = [d for d, _ in clean if last is not None and d <= last]
    todo = [(d, v) for d, v in clean if last is None or d > last]
    for d, v in todo:
        _ddb.put_item(TableName=PRICE_TABLE, Item={
            "symbol": {"S": symbol}, "date": {"S": d}, "source": {"S": src}, "source_symbol": {"S": symbol},
            "close": {"N": format(Decimal(str(v)).normalize(), "f")},
        })
    # Only when something was actually written -- a no-op re-send must not
    # throw away warm caches.
    invalidated = _invalidate(symbol) if todo else []
    return {"symbol": symbol, "written": len(todo), "skipped_existing": len(skipped),
            "last_date_before": last, "last_date_after": (todo[-1][0] if todo else last),
            "caches_invalidated": invalidated}
