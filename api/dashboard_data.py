"""
LIVE tab data: reads the nightly S3 Excel report the same way the Streamlit
app's LIVE tab does (~/market-dashboard/app.py), rather than querying
DynamoDB per-symbol. See PHASE1_SPEC.md "REVISED ARCHITECTURE" for why.

Ported from app.py: list_dashboard_dates, load_workbook, parse_hud,
parse_compass, parse_grid, _pct, HUD_GROUPS, CLOCK_Q_COLOR. Rewritten to
return plain dicts (no pandas) and extended to read the "Current Date"
column (index 15) that parse_hud never read, for per-ticker stale_days.
"""

from __future__ import annotations

import datetime
import logging
import re
from collections import OrderedDict
from io import BytesIO
from typing import Optional

import time

import boto3

REGION = "ap-southeast-1"
BUCKET = "cmon-stage-backend-369568916817-ap-southeast-1-reports"
PREFIX = "Dashboard/"
MODEL_TABLE = "cmon-stage-backend-model-history"

# Ported as-is from app.py:51-120, including CRYPTO (approved deviation #2 --
# the original spec's hud_group_order omitted it, that was an oversight).
# Tickers removed from the universe because they no longer trade (or cannot be found
# on a chart), with the evidence. Their frozen history otherwise ranked in BACKTEST,
# LIVE and the watchlists as names nobody could buy. Price rows stay in price-history;
# backtest_data filters them out of the stored blob until the nightly rebuild drops them.
# 2026-10-04, approved by the user.
RETIRED_TICKERS: dict[str, str] = {
    "PBS": "Invesco Dynamic Media ETF -- price history ends 2023-09-13",
    "JJC": "iPath copper ETN -- price history ends 2023-07-14",
    "JJN": "iPath nickel ETN -- price history ends 2023-07-14",
    "PIN": "price history ends 2023-09-01",
    "BJK": "VanEck Gaming ETF -- price history ends 2026-06-10, not found on TradingView",
    "VICE": "AdvisorShares Vice ETF -- price history ends 2026-08-28, not found on TradingView",
    "CNCR": "Range Cancer Therapeutics ETF -- not found on TradingView",
    # Duplicate, not dead: the same Global X Uranium ETF is also the universe's "URANIUM".
    # Both were registered under marketstack with source_symbol=URA; the updater keys on
    # source_symbol, so URANIUM kept updating and URA starved (last bar 2026-09-01).
    "URA": "duplicate of URANIUM (same ETF); starved by a shared source_symbol since 2026-09-01",
}

HUD_GROUPS: "OrderedDict[str, tuple]" = OrderedDict([
    ("US EQUITIES", (["DJI", "SPX", "IXIC", "RUT", "VIX"], "SPX")),
    ("INDEX ETF", (["DIA", "SPY", "QQQ", "IWM"], "SPX")),
    ("SECTOR ETF", (
        ["XLB", "XLI", "XLY", "XLC", "XLK", "XME", "XLRE", "XLP", "XLU",
         "XLE", "XOP", "XHB", "PBJ", "PEJ", "TAN", "ICLN",
         "XLF", "KBE", "KRE", "KIE", "IAI", "XLV", "XHE",
         "IYT", "JETS", "BLOK", "SOCL", "SOXX", "ROBO", "SKYY",
         "FDN", "HACK", "CIBR", "KWEB", "MJ",
         "ARKK", "ARKG", "ARKW", "ARKF", "ARKQ", "IZRL",
         # 2026-09-23: onboarded-but-unwired ETFs brought onto LIVE (and so
         # into the backtest universe). Tested first -- none is redundant
         # with XLK: the highest correlation of 20d relative strength vs
         # XLK's own is SMH at 0.45, WCLD/SOCL/ROBO ~0.15, and IBB/ITA/
         # XRT/VNQ/KRE are negative. MAGS closes the gap that missed the
         # Magnificent-7 breakout; FNGU and UVXY deliberately left out
         # (leveraged, their multi-month returns are compounding drag).
         "SMH", "MAGS", "AIQ", "WCLD",            # semis / AI / cloud
         "IBB", "IHI", "IHE", "IYH",              # healthcare depth
         "ITA", "XAR",                            # aerospace & defense
         "VNQ", "MORT",                           # real estate
         "XRT", "IBUY",                           # retail
         "KCE", "KBWP", "PSP",                    # capital markets, insurance, PE
         "ESPO",                                   # gaming
         "IDRV", "KARS", "BATT",                  # EV and batteries
         "GRID", "FAN", "PBD", "NLR", "EVX",      # grid, wind, clean, nuclear, environmental
         "SEA", "IGF",                            # shipping; global infrastructure
         # 2026-10-09: sub-sector legs for the themes (research/theme_legs/PLAN.md). Each joined only if
         # its 20d relative strength correlated < 0.90 with the theme's existing legs (it adds information)
         # and it has >= 400 days of history; none is leveraged. Near-duplicates (PSI, XSW, CLOU, BUG,
         # IHAK, RING, SILJ, URNM, PPA, FCG, XES, PXE, ENFR, IYH, KBWB, IAT, ITB, LIT, BKCH, MCHI, VEGI,
         # IAK) were left out.
         "XBI", "IHF", "XPH",                     # biotech, providers, pharma (ARKG/IHE/XHE already here)
         "IGV",                                   # software
         "BOTZ", "CHAT", "THNQ",                  # robotics & AI, generative AI, AI
         "XSD",                                   # equal-weight semis
         "NUKZ",                                  # nuclear renaissance
         "SHLD", "ARKX",                          # defense tech, space & defense
         "REZ",                                   # residential REITs
         "BOAT",                                  # global shipping
         "PAVE", "IFRA",                          # US infrastructure build-out
         "DRIV",                                  # autonomous & EV
         "QCLN", "PBW",                           # clean energy
         "WGMI",                                  # bitcoin miners
         "CQQQ",                                  # China technology
         "PHO", "CGW"],                           # water
        "SPX",
    )),
    ("US INTEREST RATES", (["US03MY", "US01Y", "US02Y", "US05Y", "US10Y", "US20Y", "US30Y", "MOVE"], None)),
    ("BONDS ETF", (["SHY", "IEF", "TLT", "TMF"], "SPX")),
    ("SPREADS", (["T10Y2Y", "T10Y3M"], None)),
    ("RATES", (["DFEDTARU", "FEDFUNDS", "CPIAUCSL", "GDP", "DRTSCILM"], None)),
    ("COMMODITIES METALS", (
        ["DBC", "USO", "UNG", "GLD", "GDX", "GDXJ", "SLV", "SIL",
         "CPER", "WOOD", "SLX", "COPX",
         # energy value chain -- the split the user's own watchlist lacks:
         # upstream E&P (IEO), oilfield services (OIH), gas producers (FCG),
         # midstream (MLPX), refiners (CRAK). XOP/XLE already cover E&P and
         # integrated. Refiners matter separately: crack spreads widen when
         # crude falls, so CRAK trades opposite IEO in exactly the regimes
         # that matter.
         "IEO", "OIH", "FCG", "MLPX", "CRAK",
         # 2026-10-09: theme legs (research/theme_legs/PLAN.md): diversified miners, rare earths,
         # MLPs and energy infrastructure, agribusiness equities.
         "PICK", "REMX", "AMLP", "EMLP", "MOO"],
        "USCI",
    )),
    ("COMMODITIES CONT.", (
        ["USCI", "USOIL", "NATGAS", "XAUUSD", "SILVER", "COPPER",
         "NICKEL", "LITHIUM", "SLX", "WOOD", "URANIUM", "COAL"],
        "USCI",
    )),
    ("AGRICULTURAL", (["DBA", "WEAT", "SOYB", "CORN", "RICE", "CANE", "COTTON"], "DBA")),
    ("COUNTRY ETF", (
        ["EWQ", "KWEB", "FXI", "EWJ", "EWZ", "EWT", "EWG", "EWH", "EWI",
         "EWW", "EWU", "IDX", "VNM", "EWM", "EIDO", "EPHE",
         "EWY", "EWA", "EWC", "EWS", "EWP", "EWL", "EZA", "INDA"],
        "SPX",
    )),
    ("FOREIGN RATES", (
        ["JP10Y", "CN10Y", "HK10Y", "PH10Y", "EU10Y", "GB10Y",
         "FR10Y", "DE10Y", "IT10Y", "ES10Y", "SG10Y", "KR10Y"],
        None,
    )),
    ("FX", (
        ["USDPHP", "USDJPY", "USDCNY", "USDAUD", "USDEUR", "USDGBP",
         "USDCHF", "USDSGD", "USDKRW", "USDHKD", "USDIDR", "USDINR",
         "USDRUB", "USDTHB", "USDTRY",
         # 2026-10-03: the six COUNTRIES rows that read "no pair". Loaded
         # from FRED's DEX* daily spot rates -- free, back to 1971 for CAD
         # and MYR, and maintained by the existing fred-data-updater, so
         # none of these joins the token-dependent refresh routine.
         # Vietnam is deliberately absent: FRED has no VND series (DEXVZUS
         # is VENEZUELA), and the dong is a crawling peg.
         "USDCAD", "USDMXN", "USDZAR", "USDBRL", "USDTWD", "USDMYR",
         "DXY", "UUP"],
        "DXY",
    )),
    ("CRYPTO", (["BTC", "ETH", "BITO"], "DXY")),
])

# A retired ticker must not drift back into the universe through a later edit.
_back = sorted(t for g in HUD_GROUPS.values() for t in g[0] if t in RETIRED_TICKERS)
assert not _back, f"retired tickers are back in HUD_GROUPS: {_back}"

HUD_GROUP_ORDER = list(HUD_GROUPS.keys())

# Ported as-is from app.py:49 / app.py:36-47.
CLOCK_Q_COLOR = {1: "#E87722", 2: "#00C851", 3: "#88DD44", 4: "#FF4444"}
GRID_Q_LABELS = {
    1: "G1 — Goldilocks",
    2: "G2 — Reflation",
    3: "G3 — Inflation",
    4: "G4 — Deflation",
}
COMPASS_Q_LABELS = {
    1: "C1 — Liquidity↑ Credit↓",
    2: "C2 — Liquidity↑ Credit↑",
    3: "C3 — Liquidity↓ Credit↑",
    4: "C4 — Liquidity↓ Credit↓",
}


def _pct(current, ref) -> Optional[float]:
    """Ported as-is from app.py:238."""
    try:
        if ref and ref != 0:
            return (current - ref) / abs(ref) * 100
    except (TypeError, ZeroDivisionError):
        pass
    return None


# Short memo over the workbook listing.
#
# list_dashboard_dates paginates EVERY nightly workbook ever written, on
# every /api/live request, in order to take element [0]. LIVE and TAPE both
# call it, and TAPE awaits nothing else -- measured, /tape took 4.35s while
# a cached endpoint on the same instance answered in 0.67s.
#
# A new workbook appears once a night (the dashboard generator runs 00:30
# UTC), so minutes of staleness on this list cannot matter; the list is only
# used to find the newest date, and the workbook behind it is separately
# ETag-checked on every load.
_DATES_TTL_SECONDS = 300.0
_dates_cache: dict[str, object] = {"at": 0.0, "dates": None}


def list_dashboard_dates(force: bool = False) -> list[str]:
    """Ported from app.py:213. Returns ISO date strings, descending."""
    if not force:
        cached = _dates_cache["dates"]
        if cached is not None and (time.monotonic() - float(_dates_cache["at"])) < _DATES_TTL_SECONDS:
            return cached  # type: ignore[return-value]

    s3 = boto3.client("s3", region_name=REGION)
    paginator = s3.get_paginator("list_objects_v2")
    dates = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            fname = obj["Key"].rsplit("/", 1)[-1]
            m = re.match(r"dashboard_(\d{4}-\d{2}-\d{2})\.xlsx$", fname)
            if m:
                dates.append(m.group(1))
    out = sorted(dates, reverse=True)
    _dates_cache["at"], _dates_cache["dates"] = time.monotonic(), out
    return out


# In-process memo of the parsed workbook, keyed by date and invalidated by
# ETag. The nightly .xlsx was downloaded from S3 and re-parsed by openpyxl on
# EVERY /api/live request -- measured at 2.7s to 12.0s per call, wildly
# variable, and the single largest remaining cost on LIVE once the backtest
# blob was fixed. The file is written once a night, so an ETag check (tens of
# milliseconds) picks up a new one immediately and costs nothing in between.
#
# One date is kept, not a dictionary of them: LIVE only ever asks for the
# newest, and holding several parsed workbooks would trade latency for memory
# on an instance that has already been memory-bound once.
_wb_cache: dict[str, object] = {"key": None, "etag": None, "wb": None, "last_modified": None}


def load_workbook(date_str: str):
    """Ported from app.py:230. Returns (openpyxl.Workbook, s3_last_modified: datetime)."""
    import openpyxl

    s3 = boto3.client("s3", region_name=REGION)
    key = f"{PREFIX}dashboard_{date_str}.xlsx"
    head = s3.head_object(Bucket=BUCKET, Key=key)
    etag = head.get("ETag")
    if (_wb_cache["key"] == key and _wb_cache["etag"] == etag
            and _wb_cache["wb"] is not None):
        return _wb_cache["wb"], _wb_cache["last_modified"]

    obj = s3.get_object(Bucket=BUCKET, Key=key)
    wb = openpyxl.load_workbook(BytesIO(obj["Body"].read()), data_only=True)
    _wb_cache.update(key=key, etag=etag, wb=wb, last_modified=obj["LastModified"])
    return wb, obj["LastModified"]


# The PARSED records, memoised by the same ETag as the workbook itself.
#
# _wb_cache already avoided re-downloading and re-opening the .xlsx, but
# parse_hud / parse_compass / parse_grid still re-walked the worksheets on
# every request -- roughly 200 HUD tickers of cell-by-cell iteration, on an
# instance with 0.1 CPU. Caching the workbook but not the parse meant paying
# the interpreted half of the cost every time.
#
# Keyed on the ETag, not a timer, so a new nightly workbook is picked up on
# the very next request and never any later.
_parsed_cache: dict[str, object] = {"key": None, "etag": None, "value": None}


def _parsed_workbook(date_str: str):
    """(wb, last_modified, hud_records, compass_tuple, grid_tuple)."""
    wb, last_modified = load_workbook(date_str)
    key, etag = _wb_cache["key"], _wb_cache["etag"]
    if (_parsed_cache["key"] == key and _parsed_cache["etag"] == etag
            and _parsed_cache["value"] is not None):
        hud, compass, grid = _parsed_cache["value"]  # type: ignore[misc]
        return wb, last_modified, hud, compass, grid

    names = wb.sheetnames  # [HUD, COMPASS, GRID, CLOCK]
    hud = parse_hud(wb[names[0]])
    compass = parse_compass(wb[names[1]])
    grid = parse_grid(wb[names[2]])
    _parsed_cache.update(key=key, etag=etag, value=(hud, compass, grid))
    return wb, last_modified, hud, compass, grid


def parse_hud(ws) -> list[dict]:
    """
    Adapted from app.py:247 (parse_hud). Returns plain dicts, not a
    DataFrame (approved deviation #4). Extended to read the "Current Date"
    column (row index 15) that the original never read, for stale_days.
    Column layout confirmed empirically against a live workbook (2026-09-04):
      0 Symbol, 2/4/6/8/10/12/14 Reference Value 1D/5D/7D/1M/3M/6M/1Y,
      15 Current Date, 16 Current Value, 18 STD-7D, 19 EMA-7D.
    """
    today = datetime.date.today()
    records = []
    current_sector = "Unknown"
    for row in ws.iter_rows(min_row=2, values_only=True):
        symbol = row[0] if row else None
        if symbol is None:
            continue
        cur_val = row[16] if len(row) > 16 else None
        if cur_val is None:
            current_sector = str(symbol)
            continue
        ref1d = row[2] if len(row) > 2 else None
        ref5d = row[4] if len(row) > 4 else None
        ref7d = row[6] if len(row) > 6 else None
        ref1m = row[8] if len(row) > 8 else None
        ref3m = row[10] if len(row) > 10 else None
        ref6m = row[12] if len(row) > 12 else None
        ref1y = row[14] if len(row) > 14 else None
        cur_date = row[15] if len(row) > 15 else None
        ema7d = row[19] if len(row) > 19 else None

        stale_days = None
        if cur_date:
            try:
                cur_date_parsed = datetime.date.fromisoformat(str(cur_date)[:10])
                stale_days = (today - cur_date_parsed).days
            except ValueError:
                pass

        records.append({
            "symbol": str(symbol),
            "sector": current_sector,
            "current": cur_val,
            "ema_7d": ema7d,
            "sd_7d": row[18] if len(row) > 18 else None,
            "pct_1d": _pct(cur_val, ref1d),
            "pct_5d": _pct(cur_val, ref5d),
            "pct_7d": _pct(cur_val, ref7d),
            "pct_1m": _pct(cur_val, ref1m),
            "pct_3m": _pct(cur_val, ref3m),
            "pct_6m": _pct(cur_val, ref6m),
            "pct_1y": _pct(cur_val, ref1y),
            "as_of": str(cur_date)[:10] if cur_date else None,
            "stale_days": stale_days,
        })

    # de-dupe by symbol, keep first (matches app.py's drop_duplicates(keep="first"))
    seen = set()
    deduped = []
    for r in records:
        if r["symbol"] in seen:
            continue
        seen.add(r["symbol"])
        deduped.append(r)
    return deduped


def _parse_quadrant_block(ws) -> tuple[list[dict], Optional[int], Optional[str]]:
    """
    Shared shape between parse_compass (app.py:288) and parse_grid (app.py:324):
    row[0]=label, quadrant/since embedded in a "Quadrant (since YYYY-MM-DD)"
    row, row[1]=quadrant int. Ref/Cur column positions differ between the two
    sheets (confirmed empirically), so this returns raw rows for the caller
    to interpret, plus the shared quadrant/since parse.
    """
    metrics_rows = []
    quadrant, since = None, None
    for row in ws.iter_rows(values_only=True):
        if row[0] is None:
            continue
        label = str(row[0])
        if label.startswith("Quadrant"):
            try:
                quadrant = int(row[1])
            except (TypeError, ValueError):
                pass
            m = re.search(r"since (\d{4}-\d{2}-\d{2})", label)
            since = m.group(1) if m else None
            break
        if label in ("Symbol", "Metrics"):
            continue
        metrics_rows.append(row)
    return metrics_rows, quadrant, since


def parse_compass(ws) -> tuple[dict, Optional[int], Optional[str]]:
    """
    Adapted from app.py:288. COMPASS sheet columns (confirmed empirically):
    0 Symbol(label), 1 Reference Date, 2 Reference Value, 3 Current Date,
    4 Current Value, 5 % Change, 6 Trend, 7 Rate.
    Returns metrics as a dict keyed by the RAW label from the sheet (e.g.
    "DFEDTARU", "DRTSCILM") -- see build report re: spec's example keys
    (fed_funds/sofr/bank_lending_pct_yoy) not matching what's actually in
    the sheet.
    """
    rows, quadrant, since = _parse_quadrant_block(ws)
    metrics = {}
    for row in rows:
        label = str(row[0])
        ref_val = row[2] if len(row) > 2 else None
        cur_val = row[4] if len(row) > 4 else None
        if cur_val is not None and isinstance(cur_val, (int, float)):
            metrics[label] = {
                "reference_date": str(row[1]) if len(row) > 1 and row[1] else None,
                "reference_value": ref_val,
                "current_date": str(row[3]) if len(row) > 3 and row[3] else None,
                "current_value": cur_val,
                "pct_change": _pct(cur_val, ref_val) if ref_val is not None else None,
            }
    return metrics, quadrant, since


def parse_grid(ws) -> tuple[dict, Optional[int], Optional[str]]:
    """
    Adapted from app.py:324. GRID sheet columns (confirmed empirically):
    0 Metrics(label), 1 Release Date, 2 Previous Value, 3 Current Value,
    4 % Change (sheet computes this itself, no separate current-date column
    on this sheet -- unlike COMPASS).
    """
    rows, quadrant, since = _parse_quadrant_block(ws)
    metrics = {}
    for row in rows:
        label = str(row[0])
        cur = row[3] if len(row) > 3 else None
        if cur is not None and isinstance(cur, (int, float)):
            prev = row[2] if len(row) > 2 else None
            pct_raw = row[4] if len(row) > 4 else None
            metrics[label] = {
                "release_date": str(row[1]) if len(row) > 1 and row[1] else None,
                "previous_value": prev,
                "current_value": cur,
                "pct_change": pct_raw if isinstance(pct_raw, (int, float)) else None,
            }
    return metrics, quadrant, since


def model_history_fallback(model_name: str) -> Optional[int]:
    """
    Approved deviation #3: if a sheet's quadrant parses as None, query
    model-history directly (PK model_name, SK metrics_date) for the latest
    quadrant, rather than the Streamlit-only local-parquet-cache fallback
    (which doesn't apply to a stateless FastAPI request).
    """
    ddb = boto3.client("dynamodb", region_name=REGION)
    resp = ddb.query(
        TableName=MODEL_TABLE,
        KeyConditionExpression="model_name = :m",
        ExpressionAttributeValues={":m": {"S": model_name}},
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp.get("Items", [])
    if not items:
        return None
    q = items[0].get("quadrant", {}).get("N")
    return int(float(q)) if q is not None else None


# ── price-history fallback for HUD rows ──────────────────────────────────────
# TAPE renders HUD_GROUPS from a workbook written by the legacy pipeline, so
# any ticker added to a group after that pipeline was frozen simply vanished
# from the scan -- which is why the 38 ETFs wired in on 2026-09-23 were fully
# backtested but invisible. These rows are computed from price-history instead,
# with the same fields parse_hud produces, so the two sources are
# interchangeable from the UI's point of view.

_PRICE_TABLE = "cmon-stage-backend-price-history"
_LOOKBACK = {"pct_1d": 1, "pct_5d": 5, "pct_7d": 7, "pct_1m": 21, "pct_3m": 63,
             "pct_6m": 126, "pct_1y": 252}


_ddb_shared = None


def _ddb_client():
    global _ddb_shared
    if _ddb_shared is None:
        _ddb_shared = boto3.client("dynamodb", region_name=REGION)
    return _ddb_shared


def _recent_closes(symbol: str, limit: int = 300) -> list[tuple[str, float]]:
    ddb = _ddb_client()
    rows: list[tuple[str, float]] = []
    resp = ddb.query(
        TableName=_PRICE_TABLE,
        KeyConditionExpression="symbol = :s",
        ExpressionAttributeValues={":s": {"S": symbol}},
        ProjectionExpression="#d, #c",
        ExpressionAttributeNames={"#d": "date", "#c": "close"},
        ScanIndexForward=False,
        Limit=limit,
    )
    for it in resp.get("Items", []):
        c = it.get("close", {}).get("N")
        if c is not None:
            rows.append((it["date"]["S"], float(c)))
    rows.sort()
    return rows


# Only these trade at weekends. A weekend-dated bar on anything else is not a close (2026-09/10: the Yahoo
# updater stored a Sunday-evening futures session as a day), so it is never used as one.
WEEKEND_TRADING = {"BTC", "ETH"}


def hud_from_price_history(symbol: str, sector: str) -> Optional[dict]:
    rows = _recent_closes(symbol)
    if symbol not in WEEKEND_TRADING:
        rows = [(d, c) for d, c in rows if datetime.date.fromisoformat(d).weekday() < 5]
    if len(rows) < 2:
        return None
    dates = [d for d, _ in rows]
    closes = [c for _, c in rows]
    cur = closes[-1]
    n = len(closes)

    out = {"symbol": symbol, "sector": sector, "current": cur}
    for field, back in _LOOKBACK.items():
        j = n - 1 - back
        out[field] = _pct(cur, closes[j]) if j >= 0 and closes[j] else None

    win = closes[-7:]
    if len(win) >= 2:
        mean = sum(win) / len(win)
        out["sd_7d"] = round((sum((x - mean) ** 2 for x in win) / len(win)) ** 0.5, 4)
        k = 2.0 / 8.0
        ema = win[0]
        for v in win[1:]:
            ema = v * k + ema * (1 - k)
        out["ema_7d"] = round(ema, 4)
    else:
        out["sd_7d"] = out["ema_7d"] = None

    out["as_of"] = dates[-1]
    try:
        out["stale_days"] = (datetime.date.today() - datetime.date.fromisoformat(dates[-1])).days
    except ValueError:
        out["stale_days"] = None
    return out


def build_live_response(date_str: Optional[str] = None) -> dict:
    available = list_dashboard_dates()
    if not available:
        raise RuntimeError("No dashboard reports found in S3")
    resolved_date = date_str if date_str in available else available[0]

    wb, last_modified, hud_records, compass, grid = _parsed_workbook(resolved_date)
    compass_metrics, compass_q, compass_since = compass
    grid_metrics, grid_q, grid_since = grid

    compass_stale_note = None
    if compass_q is None:
        compass_q = model_history_fallback("compass_US")
        if compass_q is not None:
            compass_stale_note = "Quadrant from live model-history fallback; not present in today's report."

    grid_stale_note = None
    if grid_q is None:
        grid_q = model_history_fallback("grid_US")
        if grid_q is not None:
            grid_stale_note = "Quadrant from live model-history fallback; not present in today's report."

    hud_by_symbol = {r["symbol"]: r for r in hud_records}

    # The workbook can be older than the prices we already hold: in Oct 2026 the price source started
    # publishing late, the nightly metrics step never caught up, and the workbook served the Sep 30 close for
    # a week. When that happens, rebuild the stale rows from price-history -- the same way rows the workbook
    # lacks are built below -- and say so in the payload. Never fatal: on any error the workbook rows stand.
    hud_note = None
    try:
        wb_spy = (hud_by_symbol.get("SPY") or {}).get("as_of")
        px = _recent_closes("SPY", limit=1)
        px_spy = px[-1][0] if px else None
        if wb_spy and px_spy and wb_spy < px_spy:
            behind = [(sym, r.get("sector") or "Unknown") for sym, r in hud_by_symbol.items()
                      if (r.get("as_of") or "") < px_spy]
            import cache as _cache
            from concurrent.futures import ThreadPoolExecutor

            def _rebuild() -> dict:
                with ThreadPoolExecutor(max_workers=12) as ex:
                    rows = ex.map(lambda b: hud_from_price_history(b[0], b[1]), behind)
                    return {"px_date": px_spy, "rows": {b[0]: r for b, r in zip(behind, rows) if r}}

            rebuilt = _cache.get_or_fetch("hud_fallback", _rebuild)
            if rebuilt.get("px_date") != px_spy:
                rebuilt = _rebuild()
            for sym, row in rebuilt["rows"].items():
                if (row.get("as_of") or "") > (hud_by_symbol[sym].get("as_of") or ""):
                    hud_by_symbol[sym] = row
            hud_note = (f"Nightly workbook is behind (its SPY close is {wb_spy}); "
                        f"{len(rebuilt['rows'])} rows rebuilt from stored prices up to {px_spy}.")
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception("[live] HUD fallback to price-history failed; serving workbook rows")

    # Tickers the workbook does not carry are computed from price-history.
    # Done in parallel and cached: doing it serially added ~25s to every
    # request, which is what made LIVE and TAPE take half a minute.
    missing = [(t, g) for g, (tk, _) in HUD_GROUPS.items() for t in tk if t not in hud_by_symbol]
    extra_rows: dict[str, dict] = {}
    if missing:
        import cache as _cache

        # The cached rows remember which close they were built from. A fixed 6h TTL kept serving
        # pre-correction prices after a source was repaired (2026-10-07: MAGS and the futures stayed on
        # the Oct 2/Oct 4 rows for hours after the corrected closes were stored).
        _px = _recent_closes("SPY", limit=1)
        px_date = _px[-1][0] if _px else None

        def _compute() -> dict:
            from concurrent.futures import ThreadPoolExecutor
            out: dict[str, dict] = {}
            with ThreadPoolExecutor(max_workers=12) as ex:
                for sym, row in zip([m[0] for m in missing],
                                    ex.map(lambda m: hud_from_price_history(m[0], m[1]), missing)):
                    if row:
                        out[sym] = row
            return {"px_date": px_date, "rows": out}

        try:
            cached = _cache.get_or_fetch("hud_extra", _compute)
            if cached.get("px_date") != px_date:
                cached = _compute()
        except Exception:
            cached = _compute()
        extra_rows = cached.get("rows", {})

    hud_groups = []
    for group_name, (tickers, rs_denom) in HUD_GROUPS.items():
        group_tickers = []
        for t in tickers:
            if t in hud_by_symbol:
                group_tickers.append(hud_by_symbol[t])
            elif t in extra_rows:
                group_tickers.append(extra_rows[t])
        hud_groups.append({
            "name": group_name,
            "default_rs_denom": rs_denom,
            "tickers": group_tickers,
        })

    return {
        "as_of": resolved_date,
        "generated_at": last_modified.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "compass": {
            "quadrant": compass_q,
            "label": COMPASS_Q_LABELS.get(compass_q),
            "since": compass_since,
            "stale_note": compass_stale_note,
            "metrics": compass_metrics,
        },
        "grid": {
            "quadrant": grid_q,
            "label": GRID_Q_LABELS.get(grid_q),
            "since": grid_since,
            "stale_note": grid_stale_note,
            "metrics": grid_metrics,
        },
        "hud_groups": hud_groups,
        "hud_group_order": HUD_GROUP_ORDER,
        "hud_note": hud_note,
    }
