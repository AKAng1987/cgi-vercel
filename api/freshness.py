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

SCHEMA_VERSION = 6  # 6: refresh-routine heartbeat

# How far apart two copies of the same observation may be before it is a
# disagreement rather than a rounding difference between two float paths.
VALUE_TOLERANCE = 1e-6

# How far back to look for a date both sides hold. A week of rows absorbs an
# offset publication calendar and a short holiday without absorbing a feed
# that has genuinely stopped.
COMPARE_WINDOW = 12

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


def _recent(symbol: str, n: int = 12) -> dict:
    """Our newest n rows as {date: value}.

    Needed because two feeds of the same series do not publish on the same
    days. Looking our value up at the SOURCE's newest date alone reports a
    defect whenever the calendars are merely offset -- which is what the
    us_treasury feed and FRED do routinely, and what made all seven Treasury
    tenors read as broken.
    """
    resp = _ddb.query(
        TableName=PRICE_TABLE,
        KeyConditionExpression="#s = :s",
        ExpressionAttributeNames={"#s": "symbol", "#d": "date", "#c": "close"},
        ExpressionAttributeValues={":s": {"S": symbol}},
        ProjectionExpression="#d, #c",
        ScanIndexForward=False,
        Limit=n,
    )
    return {it["date"]["S"]: float(it["close"]["N"])
            for it in resp.get("Items", []) if "close" in it}


def _value_on(symbol: str, date_iso: str) -> Optional[float]:
    """Our value for one exact date, or None if we hold no row for it."""
    resp = _ddb.get_item(
        TableName=PRICE_TABLE,
        Key={"symbol": {"S": symbol}, "date": {"S": date_iso}},
        ProjectionExpression="#c",
        ExpressionAttributeNames={"#c": "close"},
    )
    item = resp.get("Item")
    if not item or "close" not in item:
        return None
    return float(item["close"]["N"])


def _age_days(date_iso: str, today: Optional[dt.date] = None) -> int:
    t = today or dt.date.today()
    return (t - dt.date.fromisoformat(date_iso)).days


def _sessions_since(date_iso: str, today: Optional[dt.date] = None) -> int:
    """Weekdays elapsed, for judging a DAILY series.

    Calendar days lie about daily market data over a weekend: a series
    current to Friday close is three calendar days old on Monday and one
    session behind. Without this every daily symbol would look two days
    stale every Monday, which is the fastest way to make a freshness read
    worth ignoring. Holidays are not modelled -- this is a hint, and being
    wrong by one session on Thanksgiving costs nothing.
    """
    t = today or dt.date.today()
    d = dt.date.fromisoformat(date_iso)
    n = 0
    while d < t:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


# The refresh routine's heartbeat.
#
# The routine is an LLM session, so it dies when the token budget does --
# which it did on 2026-10-01 ("you've hit your weekly limit"), and the
# 2026-10-02 run then hung for fifteen hours. Nothing reported either. The
# breadth series went five sessions stale and were found by eye.
#
# Every other check here asks "is the data behind its source". None of them
# can answer "is the thing that updates the data still alive", because a
# routine that never runs leaves data that is merely old, and old is not by
# itself a defect -- PHCBBS has been correct and 240 days old all year.
#
# So the routine says so itself. One object, written on success. It catches
# the token limit, a closed app, a hung run and a deleted routine alike,
# and needs to know nothing about what any source holds.
HEARTBEAT_KEY = "refresh_routine"
HEARTBEAT_STALE_HOURS = 48.0


def _heartbeat_path() -> str:
    import cache
    return f"{cache.PREFIX}heartbeat/{HEARTBEAT_KEY}.json"


def read_heartbeat(today: Optional[dt.date] = None) -> dict:
    """When the manual-refresh routine last finished a run."""
    import json as _json

    import cache
    try:
        obj = cache._s3.get_object(Bucket=cache.BUCKET, Key=_heartbeat_path())
        payload = _json.loads(obj["Body"].read().decode("utf-8"))
        last = obj["LastModified"]
    except Exception as exc:  # noqa: BLE001 -- never written is a valid answer
        return {"ever_run": False,
                "why": f"no heartbeat recorded ({type(exc).__name__})",
                "stale": True,
                "detail": ("The refresh routine has never reported a successful "
                           "run. Until it does, every manual series is only as "
                           "fresh as the last hand-load.")}
    age_h = (dt.datetime.now(dt.timezone.utc) - last).total_seconds() / 3600.0
    stale = age_h > HEARTBEAT_STALE_HOURS
    return {
        "ever_run": True,
        "last_success": last.isoformat(),
        "age_hours": round(age_h, 1),
        "stale_after_hours": HEARTBEAT_STALE_HOURS,
        "stale": stale,
        "ran": payload.get("summary"),
        # Per-symbol record of when the routine last ASKED each source. The
        # planner uses it to re-check on each series' own cadence instead of
        # on the age of our copy -- see scripts/cgi_refresh.py.
        "ran_detail": payload.get("checked") or {},
        "detail": (f"The refresh routine has not completed a run in "
                   f"{age_h:.0f}h. Manual series stop updating when it stops, "
                   f"and it is an LLM session -- the usual cause is the token "
                   f"budget, a closed app, or a hung run."
                   if stale else
                   f"Refresh routine last completed {age_h:.0f}h ago."),
    }


def write_heartbeat(summary: Optional[str] = None,
                    checked: Optional[dict] = None) -> dict:
    """Called by the routine when it finishes. Records only that it ran."""
    import json as _json

    import cache
    body = {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "summary": summary, "checked": checked or {}}
    cache._s3.put_object(Bucket=cache.BUCKET, Key=_heartbeat_path(),
                         Body=_json.dumps(body).encode("utf-8"),
                         ContentType="application/json")
    return body


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
            source_tail = {r["date"].strftime("%Y-%m-%d"): float(r["value"])
                           for _, r in df.tail(COMPARE_WINDOW).iterrows()}
        except Exception as exc:  # noqa: BLE001 -- unreachable != disagreeing
            row["status"] = "source_unavailable"
            row["detail"] = str(exc)[:200]
            rows.append(row)
            continue

        if ours is None:
            row["status"] = "missing"
            row["detail"] = (f"declared as copied to {aws_symbol}, but nothing is "
                             f"in price-history under that name")
            rows.append(row)
            continue

        if row["ours_date"] < row["source_date"]:
            row["status"] = "behind"
            row["detail"] = (f"FRED has {row['source_date']}, we hold "
                             f"{row['ours_date']} -- the copy is behind")
            rows.append(row)
            continue

        # Compare on the latest date BOTH sides have, not on each side's own
        # newest. Several of these are not copies of FRED at all: the seven
        # Treasury tenors come from the US Treasury's own feed, which
        # publishes a day earlier than FRED's DGS series. Comparing newest
        # against newest reported all seven as a defect when the values agree
        # exactly wherever both have a row -- 2026-09-24 both 5.18, 2026-09-23
        # both 5.11 -- and we simply have tomorrow's row first.
        # The latest date BOTH sides hold, not the source's newest. Two feeds
        # of one series publish on different days, so an offset calendar is
        # not a defect -- it is the normal state for anything we take from a
        # faster provider than FRED.
        ours_tail = _recent(aws_symbol, COMPARE_WINDOW)
        shared = sorted(set(ours_tail) & set(source_tail), reverse=True)
        if not shared:
            row["status"] = "no_common_date"
            row["detail"] = (f"no date in the last {COMPARE_WINDOW} rows appears on "
                             f"both sides (ours newest {row['ours_date']}, FRED's "
                             f"{row['source_date']}) -- nothing to compare")
            rows.append(row)
            continue

        on = shared[0]
        common = ours_tail[on]
        source_on = source_tail[on]
        row["compared_on"] = on
        if abs(common - source_on) > VALUE_TOLERANCE:
            row["status"] = "value_disagrees"
            row["ours_value_on_common"] = common
            row["detail"] = (f"on {on} we hold {common} and FRED has {source_on} -- "
                             f"one of them is wrong, or it is a revision the copy "
                             f"never went back for")
        elif row["ours_date"] > row["source_date"]:
            row["status"] = "leads_source"
            row["detail"] = (f"agrees with FRED on {on}, and we also "
                             f"hold {row['ours_date']} which FRED has not published. "
                             f"Expected where the AWS side is fed by a faster provider "
                             f"than FRED -- the Treasury tenors come from us_treasury "
                             f"direct. Not a defect.")
        else:
            row["status"] = "current"
        rows.append(row)

    # leads_source is healthy: values agree where both have a row and we
    # simply have one the source has not published yet.
    OK = ("current", "leads_source", "source_unavailable")
    bad = [r for r in rows if r["status"] not in OK]
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
            # Sessions, not calendar days, for anything daily -- see
            # _sessions_since. Reported alongside so the difference is
            # visible rather than hidden in the arithmetic.
            "sessions_behind": (_sessions_since(ours["date"], t)
                                if ours and cadence == "daily" else None),
            # A HINT, not a verdict: worth looking at first, not proof of
            # anything. The routine decides by asking the source.
            "periods_behind": (
                round(_sessions_since(ours["date"], t) / 1.0, 1)
                if ours and cadence == "daily"
                else round(age / period, 1) if age is not None and period else None),
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
    beat = read_heartbeat(today)
    return {
        "as_of": (today or dt.date.today()).isoformat(),
        "automated": fred,
        "manual": manual,
        "refresh_routine": beat,
        "n_problems": (fred["n_problems"] + manual["n_never_loaded"]
                       + (1 if beat.get("stale") else 0)),
        "schema_version": SCHEMA_VERSION,
        "what_this_is": (
            "Whether our data is BEHIND ITS SOURCE -- not whether it is old. "
            "Age alone is not a defect: a monthly series is 30 days old the "
            "day before its next print, and a source that has stopped "
            "publishing leaves correct data that keeps ageing."),
    }
