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
Worst case for abuse is a few bogus recent rows on one of six symbols,
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
    return {"symbol": symbol, "written": len(todo), "skipped_existing": len(skipped),
            "last_date_before": last, "last_date_after": (todo[-1][0] if todo else last)}
