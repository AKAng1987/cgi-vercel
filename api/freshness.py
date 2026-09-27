"""
freshness.py -- is our data behind its source?

NOT "is our data old". Those are different questions and conflating them is
why the staleness alarm designed in market-dashboard/STALENESS_ALARM_DESIGN.md
should not be built as specified.

Checked 2026-09-27 against the actual sources:

    PHCBBS   ours 2026-02-01   source 2026-02-01   <- 238 days old, and CORRECT
    PHM2     ours 2026-07-01   source 2026-07-01   <- 88 days old, and CORRECT
    USBCOI   ours 2026-08-01   source 2026-08-01   <- 57 days old, and CORRECT

Every one of those would have tripped an age rule. None of them is a missed
pull; they are the publication lags of BSP, BSP and ISM. An alarm that fires
daily on data that is already correct is an alarm that gets muted, and then
it is not an alarm at all.

So the verdict here is always a COMPARISON against what the source actually
has, never an age. Age appears only as context beside the comparison.

Two halves, because the API can reach one set of sources and not the other:

  FRED half   -- the ~11 series a nightly Lambda copies into price-history.
                 The API can call FRED, so it can do the whole comparison
                 itself, and that comparison is free: two independently
                 maintained copies that should agree. If they stop agreeing,
                 either the Lambda died or FRED revised something the Lambda
                 never went back for.

  MANUAL half -- everything in series_write.ALLOWED, sourced from
                 TradingView. The API has NO TradingView client (it is an
                 MCP, reachable only from a Claude routine), so the API
                 cannot see the source side. It reports what it holds and
                 what it expects; the routine does the comparing and the
                 fixing. Pretending otherwise here would reintroduce the age
                 rule by the back door.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

import boto3

import cache
import series_write

REGION = "ap-southeast-1"
PRICE_TABLE = "cmon-stage-backend-price-history"

_ddb = boto3.client("dynamodb", region_name=REGION)
_logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2  # 2: cross-check looks the AWS side up by its own symbol name

# How far apart two copies of the same observation may be before it is a
# disagreement rather than a rounding difference between two float paths.
VALUE_TOLERANCE = 1e-6

FREQ_CADENCE = {"1D": "daily", "1W": "weekly", "1M": "monthly",
                "1Q": "quarterly", "1Y": "annual"}


def _newest(symbol: str) -> Optional[dict]:
    """Newest {date, value} we hold for a symbol, or None."""
    resp = _ddb.query(
        TableName=PRICE_TABLE,
        KeyConditionExpression="#s = :s",
        ExpressionAttributeNames={"#s": "symbol", "#d": "date", "#c": "close"},
        ExpressionAttributeValues={":s": {"S": symbol}},
        ProjectionExpression="#d, #c",
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp.get("Items") or []
    if not items:
        return None
    it = items[0]
    if "close" not in it:
        return None
    return {"date": it["date"]["S"], "value": float(it["close"]["N"])}


def _age_days(date_iso: str, today: Optional[dt.date] = None) -> int:
    t = today or dt.date.today()
    return (t - dt.date.fromisoformat(date_iso)).days


def fred_crosscheck(today: Optional[dt.date] = None) -> dict:
    """Compare our copy of each FRED series against FRED itself.

    This is the half that can be fully decided server-side, and it is the
    only automated freshness check in the system that is a comparison rather
    than a guess.
    """
    import macro_data

    rows = []
    for fred_id, aws_symbol in sorted(macro_data.FRED_IN_PRICE_HISTORY.items()):
        # The names differ -- FRED calls it DGS10, the nightly Lambda stores
        # it as US10Y -- which is why FRED_IN_PRICE_HISTORY is a map. Looking
        # the AWS side up by the FRED id reported all seven Treasury tenors
        # as "missing" when they were present under their own names.
        ours = _newest(aws_symbol)
        row: dict = {
            "symbol": fred_id,
            "aws_symbol": aws_symbol,
            "ours_date": ours["date"] if ours else None,
            "ours_value": ours["value"] if ours else None,
            "age_days": _age_days(ours["date"], today) if ours else None,
        }
        try:
            df = macro_data._fred_live(fred_id)
            if df.empty:
                raise RuntimeError("no observations")
            last = df.iloc[-1]
            row["source_date"] = last["date"].strftime("%Y-%m-%d")
            row["source_value"] = float(last["value"])
        except Exception as exc:  # noqa: BLE001 -- unreachable != disagreeing
            row["status"] = "source_unavailable"
            row["detail"] = str(exc)[:200]
            rows.append(row)
            continue

        if ours is None:
            row["status"] = "missing"
            row["detail"] = (f"declared as copied to {aws_symbol}, but nothing is "
                             f"in price-history under that name")
        elif row["ours_date"] < row["source_date"]:
            row["status"] = "behind"
            row["detail"] = (f"FRED has {row['source_date']}, we hold "
                             f"{row['ours_date']} -- the nightly copy is behind")
        elif row["ours_date"] > row["source_date"]:
            row["status"] = "ahead"
            row["detail"] = "we hold a date FRED does not -- investigate before trusting"
        elif abs(row["ours_value"] - row["source_value"]) > VALUE_TOLERANCE:
            row["status"] = "value_disagrees"
            row["detail"] = (f"same date {row['ours_date']}, different value: "
                             f"ours {row['ours_value']} vs FRED {row['source_value']} "
                             f"-- likely a revision the copy never went back for")
        else:
            row["status"] = "current"
        rows.append(row)

    bad = [r for r in rows if r["status"] not in ("current", "source_unavailable")]
    return {
        "series": rows,
        "n_checked": len(rows),
        "n_problems": len(bad),
        "problems": [r["symbol"] for r in bad],
        "note": ("Our copy against FRED itself. These are two independently "
                 "maintained copies of the same numbers, so agreement is "
                 "evidence and disagreement is a defect in one of them."),
    }


def manual_worklist(today: Optional[dt.date] = None) -> dict:
    """What we hold for every hand-loaded symbol, and what to fetch.

    Deliberately does NOT return a stale/fresh verdict. The source for these
    is TradingView, reachable only through an MCP the API cannot call, so the
    API genuinely does not know whether the source has moved. Saying "stale"
    from here would be the age rule again, and the age rule is wrong for
    exactly these symbols -- PHCBBS is 238 days old and entirely correct.

    What it gives the refresh routine is a derived checklist: every symbol,
    its TradingView ticker, what we hold, and how far past its nominal
    cadence that is. The routine fetches each, compares, and posts back only
    what is genuinely new. A symbol added to series_write.ALLOWED therefore
    joins the routine automatically -- which is exactly the failure that let
    38 backtest tickers go unnoticed, where the list lived in one place and
    the work in another.
    """
    t = today or dt.date.today()
    rows = []
    for symbol, (source, freq, _lo, _hi, tv) in sorted(series_write.ALLOWED.items()):
        ours = _newest(symbol)
        cadence = FREQ_CADENCE.get(freq, "unknown")
        period = cache.CADENCE_DAYS.get(cadence)
        age = _age_days(ours["date"], t) if ours else None
        row = {
            "symbol": symbol,
            "source": source,
            "source_symbol": tv,
            "frequency": freq,
            "cadence": cadence,
            "ours_date": ours["date"] if ours else None,
            "ours_value": ours["value"] if ours else None,
            "age_days": age,
            # A HINT, not a verdict: worth looking at first, not proof of
            # anything. The routine decides by asking the source.
            "periods_behind": (round(age / period, 1)
                               if age is not None and period else None),
        }
        if ours is None:
            row["action"] = "load"
            row["why"] = "nothing held at all"
        else:
            row["action"] = "check_source"
            row["why"] = (f"held to {ours['date']} ({age}d); ask {tv} whether "
                          f"anything newer exists")
        rows.append(row)

    unresolved = [{"symbol": k, "why": v} for k, v in
                  getattr(series_write, "UNRESOLVED", {}).items()]
    return {
        "series": rows,
        "n_symbols": len(rows),
        "n_never_loaded": sum(1 for r in rows if r["action"] == "load"),
        "unresolved": unresolved,
        "note": ("These are refreshed by a Claude routine, not by AWS. The API "
                 "cannot reach TradingView, so it reports what it holds and "
                 "the routine compares against the source. age_days is "
                 "CONTEXT, not a verdict: PHCBBS is 238 days old because BSP "
                 "has not published since 2026-02, which is correct data."),
    }


def build_freshness(today: Optional[dt.date] = None) -> dict:
    fred = fred_crosscheck(today)
    manual = manual_worklist(today)
    return {
        "as_of": (today or dt.date.today()).isoformat(),
        "automated": fred,
        "manual": manual,
        "n_problems": fred["n_problems"] + manual["n_never_loaded"],
        "schema_version": SCHEMA_VERSION,
        "what_this_is": (
            "Whether our data is BEHIND ITS SOURCE -- not whether it is old. "
            "Age alone is not a defect: a monthly series is 30 days old the "
            "day before its next print, and a source that has stopped "
            "publishing leaves correct data that keeps ageing."),
    }
