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
import pathlib
import logging
from typing import Optional

import boto3

import cache
import series_write

REGION = "ap-southeast-1"
PRICE_TABLE = "cmon-stage-backend-price-history"

_ddb = boto3.client("dynamodb", region_name=REGION)
_logger = logging.getLogger(__name__)

# The cache version is DERIVED from this module's own source plus the manual worklist,
# not typed. A hand-edited number has been forgotten three times for this payload: a
# change to what it contains (the worklist), then to the rule behind a flag (the
# one-night grace) both deployed correctly and were served stale for the cache's hour.
# Any edit to this file, or to series_write.ALLOWED, now invalidates the cached copy.
import hashlib as _hashlib

SCHEMA_VERSION = int(_hashlib.sha1(
    (pathlib.Path(__file__).read_bytes() + ",".join(sorted(series_write.ALLOWED)).encode())
).hexdigest()[:8], 16)

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
# The scheduled task runs Monday to Saturday, so the normal Saturday -> Monday gap is
# already about 48h plus the run's own duration (Oct 3 -> Oct 5: success at 05:49 UTC,
# next run starting 01:34 UTC and finishing hours later). 48h therefore sat exactly on the
# weekly gap and would have near-false-alarmed every Monday. 60h clears it with margin
# while a missed weekday run (>= 72h by the next morning) is still caught.
HEARTBEAT_STALE_HOURS = 60.0


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
        "referee_bars": payload.get("referee") or {},
        "detail": (f"The refresh routine has not completed a run in "
                   f"{age_h:.0f}h. Manual series stop updating when it stops, "
                   f"and it is an LLM session -- the usual cause is the token "
                   f"budget, a closed app, or a hung run."
                   if stale else
                   f"Refresh routine last completed {age_h:.0f}h ago."),
    }


def write_heartbeat(summary: Optional[str] = None,
                    checked: Optional[dict] = None,
                    referee_bars: Optional[dict] = None) -> dict:
    """Called by the routine when it finishes. Records only that it ran."""
    import json as _json

    import cache
    body = {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "summary": summary, "checked": checked or {}, "referee": referee_bars or {}}
    cache._s3.put_object(Bucket=cache.BUCKET, Key=_heartbeat_path(),
                         Body=_json.dumps(body).encode("utf-8"),
                         ContentType="application/json")
    return body


# The copy Lambda runs once a night (00:05 UTC). FRED can post the next day's value
# at any hour after that, so for up to a day we are legitimately one date behind
# with nothing wrong: on 2026-10-04 FRED had Sunday's DFEDTARU (4.0) and we held
# Saturday's (4.0) until the 00:05 run. Flagging that is the third time this check
# has cried wolf by comparing two feeds with different publication times as if they
# were one. One night of grace; a copy two or more dates behind has missed a run.
COPY_GRACE_DAYS = 1


def is_behind(ours_date: str, source_date: str) -> bool:
    return (dt.date.fromisoformat(source_date) - dt.date.fromisoformat(ours_date)).days > COPY_GRACE_DAYS


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

        if is_behind(row["ours_date"], row["source_date"]):
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


# ── feed integrity: does the REGISTRY agree with the DATA ───────────────────
#
# Every other check here asks whether a series is behind its source. These ask the
# question one level up, and each is a failure that already starved a series for weeks
# without anything saying so -- all three were found by eye:
#
#   orphan     registered under source=tradingview, which no Lambda serves, but absent
#              from series_write.ALLOWED, so the manual routine skips it too. Nothing
#              refreshes it. (The breadth series; then MAGS and UUP.)
#   collision  two symbols registered with the same (source, source_symbol). The
#              updaters key their lookup on source_symbol, so the last registration
#              overwrites the others and the rest starve. (URA starved by URANIUM.)
#   stalled    a backtest-universe ticker whose newest bar is far behind. (PBS, JJC and
#              JJN stopped in 2023 and ranked in the leaderboards for two years.)
#
# STALLED_SESSIONS is weekday-aware via _sessions_since. FRED-sourced rows are exempt
# from it: the Fed's H.10 exchange rates publish weekly with a lag, so a nine-day-old
# USDCAD is current, and they get a calendar-day allowance instead.
METRICS_TABLE = "cmon-stage-backend-metrics-source"
STALLED_SESSIONS = 5

# Fixed-date market closures that otherwise read as a stalled feed. China's onshore FX market shuts for
# Golden Week (Oct 1-7 every year): on 2026-10-08 USDCNY showed "6 sessions behind" when there was simply
# nothing to quote. Only fixed dates belong here; moving holidays (Spring Festival) stay unmodelled.
CLOSED_MMDD = {"USDCNY": [(10, d) for d in range(1, 8)]}


def _closed_sessions(symbol: str, date_iso: str, today: Optional[dt.date] = None) -> int:
    """Weekdays after `date_iso` (up to today) on which `symbol`'s market was known to be closed."""
    days = CLOSED_MMDD.get(symbol)
    if not days:
        return 0
    t, d = today or dt.date.today(), dt.date.fromisoformat(date_iso) + dt.timedelta(days=1)
    n = 0
    while d <= t:
        n += d.weekday() < 5 and (d.month, d.day) in days
        d += dt.timedelta(days=1)
    return n
STALLED_FRED_DAYS = 14


def integrity_problems(registry: list[dict], allowed: set[str], universe: list[str],
                       last_rows: dict[str, Optional[dict]],
                       today: Optional[dt.date] = None) -> dict:
    """Pure core: registry rows {source, symbol, source_symbol}, the manual worklist,
    the universe, and each ticker's newest row {date, source} -> what is wrong."""
    orphans = sorted(r["symbol"] for r in registry
                     if r["source"] == "tradingview" and r["symbol"] not in allowed)

    groups: dict[tuple, list[str]] = {}
    for r in registry:
        groups.setdefault((r["source"], r.get("source_symbol") or r["symbol"]), []).append(r["symbol"])
    collisions = [{"source": k[0], "source_symbol": k[1], "symbols": sorted(v)}
                  for k, v in sorted(groups.items()) if len(v) > 1]

    stalled = []
    for t in universe:
        row = last_rows.get(t)
        if row is None:
            stalled.append({"symbol": t, "newest": None, "behind": "no rows at all", "source": None})
            continue
        if row["source"] == "fred":
            behind_n, bad = _age_days(row["date"], today), _age_days(row["date"], today) > STALLED_FRED_DAYS
            unit = "days"
        else:
            behind_n = _sessions_since(row["date"], today) - _closed_sessions(t, row["date"], today)
            bad, unit = behind_n > STALLED_SESSIONS, "sessions"
        if bad:
            stalled.append({"symbol": t, "newest": row["date"], "behind": f"{behind_n} {unit}",
                            "source": row["source"]})
    return {"orphans": orphans, "collisions": collisions, "stalled": stalled,
            "n_problems": len(orphans) + len(collisions) + len(stalled), "checked": len(universe)}


def _registry() -> list[dict]:
    rows, kw = [], dict(TableName=METRICS_TABLE, ProjectionExpression="#src, #sym, source_symbol, frequency",
                        ExpressionAttributeNames={"#src": "source", "#sym": "symbol"})
    while True:
        page = _ddb.scan(**kw)
        rows += [{"source": i["source"]["S"], "symbol": i["symbol"]["S"],
                  "source_symbol": i.get("source_symbol", {}).get("S"),
                  "frequency": i.get("frequency", {}).get("S")} for i in page["Items"]]
        if "LastEvaluatedKey" not in page:
            return rows
        kw["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def _last_row(symbol: str) -> Optional[dict]:
    resp = _ddb.query(TableName=PRICE_TABLE, KeyConditionExpression="#s = :s",
                      ExpressionAttributeNames={"#s": "symbol", "#d": "date", "#src": "source"},
                      ExpressionAttributeValues={":s": {"S": symbol}},
                      ProjectionExpression="#d, #src", ScanIndexForward=False, Limit=1)
    it = (resp.get("Items") or [None])[0]
    return {"date": it["date"]["S"], "source": it.get("source", {}).get("S")} if it else None


def feed_integrity(today: Optional[dt.date] = None) -> dict:
    """I/O wrapper. A check that cannot run reports itself as a problem rather than as
    a healthy zero: silence from a broken guard looks identical to a clean bill."""
    try:
        import backtest_data
        from concurrent.futures import ThreadPoolExecutor
        universe = backtest_data.build_backtest_universe()[0]
        with ThreadPoolExecutor(16) as ex:
            rows = dict(zip(universe, ex.map(_last_row, universe)))
        return integrity_problems(_registry(), set(series_write.ALLOWED), universe, rows, today)
    except Exception as exc:  # noqa: BLE001
        _logger.exception("[freshness] feed_integrity could not run")
        return {"orphans": [], "collisions": [], "stalled": [], "n_problems": 1, "checked": 0,
                "error": f"{type(exc).__name__}: {exc}"}



# Pipeline lag: the nightly price -> metrics -> workbook chain can run on time and still serve old numbers.
#
# 2026-10: the price source began publishing a close a day late; the metrics step only looked for "yesterday",
# never caught up, and the workbook served the Sep 30 close for a week while every run "succeeded" and this page
# said 0 problems. Prices were only ~2 sessions behind (under STALLED_SESSIONS), so nothing here could see it.
# Two narrower questions catch it: is the workbook older than the prices we already hold, and are the
# benchmark closes themselves further behind than the source's normal one-day lateness.
PIPELINE_BENCHMARKS = ("SPY", "QQQ", "DBA")
EQUITY_BEHIND_SESSIONS = 2   # D-1 is normal, D-2 is the source's current lateness; more is a problem


def pipeline_problems(price_newest: dict[str, Optional[str]], workbook_newest: dict[str, Optional[str]],
                      today: Optional[dt.date] = None) -> dict:
    """Pure core: newest stored close and the workbook's close date per benchmark -> what is wrong."""
    problems = []
    for sym in PIPELINE_BENCHMARKS:
        p, w = price_newest.get(sym), workbook_newest.get(sym)
        if p is None:
            problems.append({"check": "equity_close_behind", "symbol": sym, "detail": "no stored close"})
            continue
        behind = _sessions_since(p, today)
        if behind > EQUITY_BEHIND_SESSIONS:
            problems.append({"check": "equity_close_behind", "symbol": sym,
                             "detail": f"newest close {p} is {behind} sessions old"})
        if w is not None and w < p and _sessions_since(w, dt.date.fromisoformat(p)) >= 1:
            problems.append({"check": "workbook_behind_prices", "symbol": sym,
                             "detail": f"workbook shows the {w} close; prices hold {p}"})
    return {"problems": problems, "n_problems": len(problems)}


def pipeline_lag(today: Optional[dt.date] = None) -> dict:
    """I/O wrapper; a check that cannot run reports itself as a problem."""
    try:
        import dashboard_data as dd
        _wb, _lm, hud, _c, _g = dd._parsed_workbook(dd.list_dashboard_dates()[0])
        wb = {r["symbol"]: r.get("as_of") for r in hud if r.get("symbol") in PIPELINE_BENCHMARKS}
        prices = {s: (_last_row(s) or {}).get("date") for s in PIPELINE_BENCHMARKS}
        out = pipeline_problems(prices, wb, today)
        out.update(price_newest=prices, workbook_newest=wb)
        return out
    except Exception as exc:  # noqa: BLE001
        _logger.exception("[freshness] pipeline_lag could not run")
        return {"problems": [], "n_problems": 1, "error": f"{type(exc).__name__}: {exc}"}



# Peer lag: one series a bar behind the rest.
#
# 2026-10-13: MAGS, UUP and the Yahoo futures sat on the 9 Oct close while the other 167 daily series held 12 Oct.
# Every check above compares against a calendar or a benchmark trio, so a single series one bar behind passed, and
# the Themes table aged MAGS at 43 days beside legs at 46. This compares each daily series with SPY's newest bar.
# Futures (Yahoo "=F") are one session behind BY DESIGN -- the updater only stores a futures bar once its ET day
# has ended -- so they are exempt. Names behind by more than STALLED_SESSIONS belong to the stalled check.
PEER_SOURCES = ("marketstack", "yahoo_finance", "alpha_vantage")
# Series that follow the US BOND market. It is shut on Columbus Day (2nd Monday of October) and Veterans Day (11 Nov)
# while stocks trade, so MOVE has no bar on those days and must not be called behind SPY (2026-10-12 was the first case).
BOND_ONLY = frozenset({"MOVE"})


def _bond_holiday(d: dt.date) -> bool:
    return (d.month == 10 and d.weekday() == 0 and 8 <= d.day <= 14) or (d.month == 11 and d.day == 11)


def peer_problems(rows: dict[str, dict], benchmark_date: Optional[str], retired: frozenset = frozenset()) -> dict:
    """Pure core: {symbol: {date, source, source_symbol}} for the daily series -> those a session or more behind SPY."""
    if not benchmark_date:
        return {"problems": [{"symbol": "SPY", "detail": "no benchmark close to compare against"}], "n_problems": 1,
                "checked": 0, "benchmark_date": None}
    bench = dt.date.fromisoformat(benchmark_date)
    problems, checked = [], 0
    for sym, r in sorted(rows.items()):
        if sym in retired or r.get("source") not in PEER_SOURCES or (r.get("source_symbol") or "").endswith("=F"):
            continue
        checked += 1
        ref = bench
        while sym in BOND_ONLY and (_bond_holiday(ref) or ref.weekday() >= 5):
            ref -= dt.timedelta(days=1)          # compare with the last day the bond market was open
        if r["date"] >= ref.isoformat():
            continue
        behind = _sessions_since(r["date"], ref)
        if 1 <= behind <= STALLED_SESSIONS:
            problems.append({"symbol": sym, "detail": f"newest {r['date']} is {behind} session(s) behind SPY ({benchmark_date})",
                             "source": r["source"]})
    return {"problems": problems, "n_problems": len(problems), "checked": checked, "benchmark_date": benchmark_date}


def peer_lag(today: Optional[dt.date] = None) -> dict:
    """I/O wrapper; a check that cannot run reports itself as a problem."""
    try:
        import dashboard_data as dd
        from concurrent.futures import ThreadPoolExecutor
        reg = [r for r in _registry() if r.get("frequency") == "1D" and r["source"] in PEER_SOURCES]
        syms = [r["symbol"] for r in reg]
        with ThreadPoolExecutor(16) as ex:
            last = dict(zip(syms, ex.map(_last_row, syms)))
        # judge by the REGISTERED source, not the newest row's: a Yahoo series the routine topped up from TradingView
        # still has to be held to the same standard
        rows = {r["symbol"]: {**last[r["symbol"]], "source": r["source"], "source_symbol": r.get("source_symbol")}
                for r in reg if last.get(r["symbol"])}
        spy = (_last_row("SPY") or {}).get("date")
        return peer_problems(rows, spy, frozenset(dd.RETIRED_TICKERS))
    except Exception as exc:  # noqa: BLE001
        _logger.exception("[freshness] peer_lag could not run")
        return {"problems": [], "n_problems": 1, "checked": 0, "error": f"{type(exc).__name__}: {exc}"}


# The jump guard: a feed can be current AND wrong by a constant factor. In Oct 2026 marketstack returned a
# gold series about ten times too high for four days (GLD 3,782 against 382); every check above passed, because
# the newest date was current, and the Backtest tab then showed GLD at "+181.92% average high" in first place.
# A real one-day move beyond JUMP_RATIO in either direction in a price series is vanishingly rare, while a
# vendor mixing up an instrument produces exactly that, twice (on the way in and on the way out). Price sources
# only: FRED-type balances such as RRPONTSYD legitimately swing by more. A genuine reverse split also trips it
# and has to be cleared by hand, which is the right amount of noise for a data-integrity alarm.
JUMP_RATIO = 3.0
JUMP_LOOKBACK = 10     # newest closes inspected per series


def jump_problems(closes: dict, retired: frozenset = frozenset()) -> dict:
    """Pure core: {symbol: [(date, close), ...] oldest first} -> one problem per series with a one-day
    move beyond JUMP_RATIO either way inside the lookback, listing every date it happened."""
    problems, checked = [], 0
    for sym, rows in sorted(closes.items()):
        if sym in retired or len(rows) < 2:
            continue
        checked += 1
        hits = []
        for (d0, c0), (d1, c1) in zip(rows, rows[1:]):
            if c0 and c1 and c0 > 0 and c1 > 0:
                ratio = c1 / c0
                if ratio > JUMP_RATIO or ratio < 1 / JUMP_RATIO:
                    hits.append(f"{d0} {c0:g} -> {d1} {c1:g} (x{ratio:.2f})")
        if hits:
            problems.append({"symbol": sym, "detail": "; ".join(hits),
                             "hint": "a price source returning the wrong instrument or scale; a real split also looks like this"})
    return {"problems": problems, "n_problems": len(problems), "checked": checked,
            "ratio": JUMP_RATIO, "lookback": JUMP_LOOKBACK}


def _close_series(symbol: str, n: int = JUMP_LOOKBACK) -> list:
    """Newest n closes, OLDEST FIRST (jump_problems compares neighbours in date order). Not _recent_closes: that name
    already belongs to the referee's helper (newest first), and a second def silently replaced this one."""
    resp = _ddb.query(TableName=PRICE_TABLE, KeyConditionExpression="#s = :s",
                      ExpressionAttributeNames={"#s": "symbol", "#d": "date", "#c": "close"},
                      ExpressionAttributeValues={":s": {"S": symbol}},
                      ProjectionExpression="#d, #c", ScanIndexForward=False, Limit=n)
    rows = [(i["date"]["S"], float(i["close"]["N"])) for i in resp.get("Items", []) if "close" in i and "N" in i["close"]]
    return sorted(rows)


def price_jumps(today: Optional[dt.date] = None) -> dict:
    """I/O wrapper; a check that cannot run reports itself as a problem."""
    try:
        import dashboard_data as dd
        from concurrent.futures import ThreadPoolExecutor
        reg = [r for r in _registry() if r.get("frequency") == "1D" and r["source"] in PEER_SOURCES]
        syms = sorted({r["symbol"] for r in reg})
        with ThreadPoolExecutor(16) as ex:
            closes = dict(zip(syms, ex.map(_close_series, syms)))
        return jump_problems(closes, frozenset(dd.RETIRED_TICKERS))
    except Exception as exc:  # noqa: BLE001
        _logger.exception("[freshness] price_jumps could not run")
        return {"problems": [], "n_problems": 1, "checked": 0, "error": f"{type(exc).__name__}: {exc}"}


# The referee: an independent second source for a handful of benchmarks.
#
# Every check above asks whether a feed is BEHIND. None can see a feed that is current and WRONG: in Oct 2026
# RUT sat on Oct 2 beside Oct 6 rows, and the futures were stored two hours into the next session with Sunday
# dates, and nothing here noticed. TradingView is a different vendor, so agreement means something. It is only
# reachable from the morning refresh session (an MCP), which sends its bars with the heartbeat; the comparison
# runs here against what is stored. Kinds set the tolerance: two feeds' closes legitimately differ a little for
# futures (settlement vs last) and FX (24h market, no single close), and our 10y is the Treasury's official
# curve rather than the traded quote.
REFEREE = {
    "SPX": ("TVC:SPX", "eq"), "DJI": ("TVC:DJI", "eq"), "IXIC": ("NASDAQ:IXIC", "eq"), "RUT": ("TVC:RUT", "eq"),
    "SPY": ("AMEX:SPY", "eq"), "QQQ": ("NASDAQ:QQQ", "eq"), "DBA": ("AMEX:DBA", "eq"), "UUP": ("AMEX:UUP", "eq"),
    "MAGS": ("CBOE:MAGS", "eq"), "VIX": ("TVC:VIX", "vol"),
    "USOIL": ("NYMEX:CL1!", "fut"), "XAUUSD": ("COMEX:GC1!", "fut"), "NATGAS": ("NYMEX:NG1!", "fut"),
    "US10Y": ("TVC:US10Y", "yield"), "USDJPY": ("FX:USDJPY", "fx"),
}
REFEREE_TOL = {"eq": 0.0015, "vol": 0.01, "fut": 0.002, "fx": 0.005}   # relative; futures closes match TradingView exactly when right
REFEREE_YIELD_TOL = 0.08                                                 # percentage points
REFEREE_BEHIND = {"fut": 3}   # TradingView shows the session in progress; futures are final a day later
REFEREE_BEHIND_DEFAULT = 2    # the price source publishes a day late, so one newer date is normal


def referee_problems(tv_bars: dict, ours: dict, today: Optional[dt.date] = None) -> dict:
    """Pure core. tv_bars {symbol: [[date, close], ...]} from TradingView; ours {symbol: [(date, close), ...]}."""
    today_iso = (today or dt.date.today()).isoformat()
    problems, checked = [], 0
    for sym, (tv, kind) in REFEREE.items():
        theirs = {d[:10]: float(c) for d, c in (tv_bars.get(sym) or []) if c is not None}
        mine = dict(ours.get(sym) or [])
        if not theirs:
            continue
        checked += 1
        if not mine:
            problems.append({"check": "referee_missing", "symbol": sym, "detail": f"nothing stored; {tv} has data"})
            continue
        worst = None
        for d in sorted(set(theirs) & set(mine)):
            a, b = mine[d], theirs[d]
            off = abs(a - b) if kind == "yield" else (abs(a - b) / abs(b) if b else 0.0)
            limit = REFEREE_YIELD_TOL if kind == "yield" else REFEREE_TOL[kind]
            if off > limit and (worst is None or off > worst[0]):
                worst = (off, d, a, b)
        if worst:
            off, d, a, b = worst
            shown = f"{off:.2f}pt" if kind == "yield" else f"{off * 100:.2f}%"
            problems.append({"check": "referee_mismatch", "symbol": sym,
                             "detail": f"{d}: we hold {a:g}, {tv} has {b:g} ({shown} apart)"})
        weekend = sorted(d for d in mine if dt.date.fromisoformat(d).weekday() >= 5)
        if weekend:
            # TradingView has no bar to compare these with, so they would pass silently: nothing but crypto closes
            # on a Saturday or Sunday (2026-10: the Yahoo updater stored Sunday-evening futures sessions).
            problems.append({"check": "referee_weekend", "symbol": sym,
                             "detail": f"weekend-dated rows stored: {', '.join(weekend)}"})
        newest = max(mine)
        # TradingView's FX bar for today is still OPEN (a currency day runs to 17:00 New York, after our nightly run), so for FX
        # only dates before today count as newer. Without this, holding the last finished day flagged "behind" against {yesterday,
        # today} whenever the threshold was two (2026-10-30: USDJPY).
        newer = [d for d in theirs if d > newest and d <= today_iso and not (kind == "fx" and d >= today_iso)]
        if len(newer) >= REFEREE_BEHIND.get(kind, REFEREE_BEHIND_DEFAULT):
            problems.append({"check": "referee_behind", "symbol": sym,
                             "detail": f"we hold {newest}; {tv} already has {max(newer)}"})
    return {"problems": problems, "n_problems": len(problems), "checked": checked}


def _recent_closes(symbol: str, n: int = 10) -> list[tuple[str, float]]:
    resp = _ddb.query(TableName=PRICE_TABLE, KeyConditionExpression="#s = :s",
                      ExpressionAttributeNames={"#s": "symbol", "#d": "date", "#c": "close"},
                      ExpressionAttributeValues={":s": {"S": symbol}},
                      ProjectionExpression="#d, #c", ScanIndexForward=False, Limit=n)
    return [(i["date"]["S"], float(i["close"]["N"])) for i in resp.get("Items", []) if "close" in i]


def referee(tv_bars: Optional[dict], today: Optional[dt.date] = None) -> dict:
    """I/O wrapper. No bars means the morning run did not send any: say so, do not invent a problem."""
    if not tv_bars:
        return {"problems": [], "n_problems": 0, "checked": 0,
                "detail": "no TradingView bars received with the last refresh"}
    try:
        from concurrent.futures import ThreadPoolExecutor
        syms = [s for s in REFEREE if tv_bars.get(s)]
        with ThreadPoolExecutor(8) as ex:
            ours = dict(zip(syms, ex.map(_recent_closes, syms)))
        return referee_problems(tv_bars, ours, today)
    except Exception as exc:  # noqa: BLE001
        _logger.exception("[freshness] referee could not run")
        return {"problems": [], "n_problems": 1, "checked": 0, "error": f"{type(exc).__name__}: {exc}"}


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


def erp_check(today: Optional[dt.date] = None) -> dict:
    """Damodaran's implied ERP. Triggers its once-a-day sync (the refresh routine reads this page each morning),
    then reports whether the newest month we hold is the one we should hold by now."""
    import erp_data
    try:
        sync = erp_data.sync_if_due()
        st = erp_data.status(today)
    except Exception as exc:  # noqa: BLE001 -- additive; never break the page
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}", "n_problems": 0}
    return {**st, "sync": sync, "n_problems": 1 if st["behind"] and not sync.get("ok") else 0,
            "note": ("behind: he has not posted this month's row yet, or the sync failed"
                     if st["behind"] else "current")}


COT_STALL_DAYS = {"weekly": 9, "twice": 6}


def cot_problems(source_newest: Optional[str], cached: Optional[dict], today: dt.date) -> dict:
    """Pure part of the COT check. `source_newest` = newest as-of date the CFTC API holds; `cached` = the COT payload we are
    serving (or None).

    STALLED: the newest report at the CFTC was published more than 9 days ago (6 once reports are twice a week). This is
    the check that notices the new twice-weekly reports landing in a different dataset: our fetch keeps answering from
    the old one and nothing else would say so.
    CADENCE: the as-of weekdays or frequency in the data are not a pattern the code knows (cot_data._cadence).
    The cached payload being behind the source is reported but is not a problem: the cache rebuilds from the source on
    the next request after its 6 h TTL."""
    import cot_data

    problems = []
    cad = (cached or {}).get("cadence") or {}
    if source_newest is None:
        problems.append({"check": "source", "detail": "the CFTC API returned no report date"})
        pub = None
    else:
        pub = cot_data.publish_date(source_newest)
        limit = COT_STALL_DAYS["twice" if cad.get("twice_weekly") else "weekly"]
        quiet = (today - pub).days
        if quiet > limit:
            problems.append({"check": "stalled",
                             "detail": (f"newest CFTC report is as of {source_newest} (published {pub.isoformat()}); "
                                        f"nothing newer for {quiet} days, expected within {limit}. If the new twice-weekly "
                                        f"reports use a different dataset, cot_data.BASE must change.")})
    if cad.get("problem"):
        problems.append({"check": "cadence", "detail": cad["problem"]})
    ours = (cached or {}).get("as_of")
    return {"problems": problems, "n_problems": len(problems), "source_newest": source_newest,
            "published_est": pub.isoformat() if pub else None, "ours_as_of": ours,
            "latest_observation": (cached or {}).get("latest_observation"),
            "cache_behind_source": bool(source_newest and ours and ours < source_newest),
            "pattern": cad.get("pattern")}


def cot_check(today: Optional[dt.date] = None) -> dict:
    """COT freshness: the CFTC's own newest report date against the payload we serve. Reads the CFTC directly (public),
    so no refresh routine is involved."""
    import json as _json
    import urllib.request as _rq

    import cache
    import cot_data

    today = today or dt.date.today()
    try:
        url = f"{cot_data.BASE}?$select=report_date_as_yyyy_mm_dd&$order=report_date_as_yyyy_mm_dd%20DESC&$limit=1"
        with _rq.urlopen(url, timeout=20) as r:
            rows = _json.load(r)
        source_newest = rows[0]["report_date_as_yyyy_mm_dd"][:10] if rows else None
        peeked = cache.peek("cot")
        out = cot_problems(source_newest, peeked[0] if peeked else None, today)
        out["cache_age_hours"] = round(peeked[1], 1) if peeked else None
        return out
    except Exception as exc:  # noqa: BLE001 -- a check that cannot run is itself a problem worth seeing
        return {"problems": [], "n_problems": 1, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}


CAPEX_FILING_LAG_DAYS = 75     # 10-Q/10-K deadlines are 40-60 days; 75 leaves room for the late filers
CAPEX_MIN_SHARE = 0.80         # share of capex reporters that must have the expected quarter
CAPEX_MAX_AGE_DAYS = 9         # weekly launchd job (Sunday 09:00 Manila); older than this means it did not run


def capex_problems(snap: Optional[dict], today: dt.date) -> dict:
    """Pure part of the capex check. `snap` is the stored snapshot (or None).

    BEHIND: the newest quarter that should be fully filed by now (quarter end + 75 days) is missing for more than
    20% of the companies that report capex at all, i.e. the snapshot predates the last earnings season.
    STALE: the snapshot itself is older than 9 days (the weekly refresh did not run).
    GAPS: more than 10% of the universe failed to load from the SEC."""
    import capex_data

    if not snap or not snap.get("companies"):
        return {"problems": [{"check": "missing", "detail": "no capex snapshot stored; run capex_build.py --upload"}],
                "n_problems": 1}
    comps = snap["companies"]
    reporters = [c for c in comps if c.get("cq")]
    expected = None
    for q in capex_data.q_range("2024Q1", "2030Q4")[::-1]:
        y, k = int(q[:4]), int(q[5])
        end = dt.date(y, k * 3, 30 if k in (2, 3) else 31)
        if end + dt.timedelta(days=CAPEX_FILING_LAG_DAYS) <= today:
            expected = q
            break
    have = sum(1 for c in reporters if expected in c["cq"]) if expected else 0
    share = have / len(reporters) if reporters else 0.0
    problems = []
    if expected and share < CAPEX_MIN_SHARE:
        problems.append({"check": "behind", "detail": (f"{have} of {len(reporters)} capex reporters have {expected} "
                                                      f"({share:.0%}, need {CAPEX_MIN_SHARE:.0%}); re-run capex_build.py --upload")})
    built = snap.get("built_at")
    age = None
    if built:
        age = (today - dt.date.fromisoformat(built[:10])).days
        if age > CAPEX_MAX_AGE_DAYS:
            problems.append({"check": "stale", "detail": f"snapshot built {built[:10]}, {age} days ago"})
    failed = len(snap.get("failed", []))
    if snap.get("n_universe") and failed / snap["n_universe"] > 0.10:
        problems.append({"check": "gaps", "detail": f"{failed} of {snap['n_universe']} companies failed to load"})
    return {"problems": problems, "n_problems": len(problems), "expected_quarter": expected,
            "share_with_expected": round(share, 3), "built_at": built, "age_days": age,
            "n_reporters": len(reporters), "n_failed": failed}


def capex_check(today: Optional[dt.date] = None) -> dict:
    """S&P 500 capex snapshot freshness. Reads the stored snapshot only; never touches the SEC."""
    import capex_data

    try:
        return capex_problems(capex_data.read_snapshot(), today or dt.date.today())
    except Exception as exc:  # noqa: BLE001 -- additive; never break the page
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}", "n_problems": 0}


CALENDAR_HORIZON_DAYS = 75     # every release type needs a scheduled date inside this window


def calendar_problems(today: dt.date, releases: Optional[list[dict]] = None) -> dict:
    """Pure part of the release-calendar check. The release dates are hardcoded (release_calendar.py); when a type runs
    out, its cards, per-release P(flip), pre-registration and scorecard go silent without any error. This says so early:
    a problem when FOMC, CPI, GDP or SLOOS has no scheduled date within the next CALENDAR_HORIZON_DAYS days."""
    import release_calendar as rc

    rel = rc.RELEASES if releases is None else releases
    end = (today + dt.timedelta(days=CALENDAR_HORIZON_DAYS)).isoformat()
    t0 = today.isoformat()
    problems, nxt = [], {}
    for kind in ("FOMC", "CPI", "GDP", "SLOOS"):
        dates = sorted(r["date"] for r in rel if r["type"] == kind and r["date"] >= t0)
        nxt[kind] = dates[0] if dates else None
        if not dates or dates[0] > end:
            problems.append({"check": kind, "detail": (f"no {kind} release scheduled in the next {CALENDAR_HORIZON_DAYS} days "
                                                       f"(next: {dates[0] if dates else 'none'}); add the new year to release_calendar.py")})
    last = max((r["date"] for r in rel), default=None)
    return {"problems": problems, "n_problems": len(problems), "next": nxt, "last_date": last}


def calendar_check(today: Optional[dt.date] = None) -> dict:
    try:
        return calendar_problems(today or dt.date.today())
    except Exception as exc:  # noqa: BLE001 -- additive; never break the page
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}", "n_problems": 0}


GDP_GRACE_DAYS = 3     # the calendar may be a day or two off a shifted BEA date (stored 26 Aug, calendar 27 Aug); a miss is a whole release


def gdp_problems(today: dt.date, newest_stored: Optional[str], releases: Optional[list[dict]] = None) -> dict:
    """Pure part of the GDP-store check. gdp-history must hold a row at or after the latest GDP release that is at least two
    days old (the updater reads ALFRED the day after a release). Before this check the scraper was blocked for three weeks
    (10 Oct onward), the 29 Oct advance estimate never reached the Grid or the headline, and nothing said so."""
    import release_calendar as rc

    rel = rc.RELEASES if releases is None else releases
    cutoff = (today - dt.timedelta(days=2)).isoformat()
    due = sorted(r["date"] for r in rel if r["type"] == "GDP" and r["date"] <= cutoff)
    latest = due[-1] if due else None
    problems = []
    if latest is not None:
        need = (dt.date.fromisoformat(latest) - dt.timedelta(days=GDP_GRACE_DAYS)).isoformat()
        if newest_stored is None or newest_stored < need:
            problems.append({"check": "gdp_history", "detail": (f"GDP released {latest} but the newest stored row is "
                                                                f"{newest_stored or 'none'}; the gdp-updater Lambda is not storing releases")})
    return {"problems": problems, "n_problems": len(problems), "latest_release": latest, "newest_stored": newest_stored}


def gdp_check(today: Optional[dt.date] = None) -> dict:
    """Newest stored GDP release (DynamoDB gdp-history) against the release calendar."""
    import boto3

    try:
        ddb = boto3.client("dynamodb", region_name="ap-southeast-1")
        r = ddb.query(TableName="cmon-stage-backend-gdp-history", KeyConditionExpression="country = :c",
                      ExpressionAttributeValues={":c": {"S": "US"}}, ScanIndexForward=False, Limit=1)
        newest = r["Items"][0]["release_date"]["S"] if r.get("Items") else None
        return gdp_problems(today or dt.date.today(), newest)
    except Exception as exc:  # noqa: BLE001 -- additive; never break the page
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}", "n_problems": 0}


def rate_path_problems(payload: Optional[dict]) -> dict:
    """Pure part of the rate-path check: enough futures quotes came back to draw a path."""
    if not payload:
        return {"problems": [{"check": "missing", "detail": "no rate path payload"}], "n_problems": 1}
    problems = []
    nq = payload.get("n_sr3_quoted", 0)
    na = sum(1 for m in payload.get("meetings", []) if m.get("available"))
    if nq < 6:
        problems.append({"check": "sofr_futures", "detail": f"only {nq} of {payload.get('n_sr3')} SOFR futures quoted (yfinance)"})
    if na < 3:
        problems.append({"check": "fed_funds_futures", "detail": f"only {na} FOMC meetings priced from fed funds futures"})
    return {"problems": problems, "n_problems": len(problems), "n_sr3_quoted": nq, "n_meetings_priced": na,
            "history_days": payload.get("history_days"), "as_of": payload.get("as_of")}


def rate_path_check() -> dict:
    """Futures-implied rate path health. Also what keeps the daily snapshot going: the morning routine reads freshness every
    day, and this refreshes the path behind it (non-blocking), which appends that day's snapshot."""
    import cache
    import rate_path

    try:
        return rate_path_problems(cache.get_or_fetch_bg("rate_path", rate_path.build_rate_path))
    except Exception as exc:  # noqa: BLE001 -- additive; never break the page
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}", "n_problems": 0}


def build_freshness(today: Optional[dt.date] = None) -> dict:
    erp = erp_check(today)
    fred = fred_crosscheck(today)
    manual = manual_worklist(today)
    beat = read_heartbeat(today)
    integrity = feed_integrity(today)
    pipeline = pipeline_lag(today)
    peers = peer_lag(today)
    jumps = price_jumps(today)
    ref = referee(beat.pop("referee_bars", None), today)
    cot = cot_check(today)
    capex = capex_check(today)
    calendar = calendar_check(today)
    gdp = gdp_check(today)
    ratepath = rate_path_check()
    return {
        "as_of": (today or dt.date.today()).isoformat(),
        "automated": fred,
        "manual": manual,
        "refresh_routine": beat,
        "feed_integrity": integrity,
        "pipeline_lag": pipeline,
        "peer_lag": peers,
        "price_jumps": jumps,
        "referee": ref,
        "erp": erp,
        "cot": cot,
        "capex": capex,
        "release_calendar": calendar,
        "gdp": gdp,
        "rate_path": ratepath,
        "n_problems": (fred["n_problems"] + manual["n_never_loaded"]
                       + (1 if beat.get("stale") else 0) + integrity["n_problems"]
                       + pipeline["n_problems"] + peers["n_problems"] + jumps["n_problems"] + ref["n_problems"] + erp["n_problems"] + cot["n_problems"] + capex["n_problems"] + calendar["n_problems"] + gdp["n_problems"] + ratepath["n_problems"]),
        "schema_version": SCHEMA_VERSION,
        "what_this_is": (
            "Whether our data is BEHIND ITS SOURCE -- not whether it is old. "
            "Age alone is not a defect: a monthly series is 30 days old the "
            "day before its next print, and a source that has stopped "
            "publishing leaves correct data that keeps ageing."),
    }
