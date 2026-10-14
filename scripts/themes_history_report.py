"""themes_history_report.py -- retroactive "themes in play", local and read-only.

Replays CGI's theme detector (api/themes_data.py) as of past month-ends, using
only price data up to each date, and writes web/app/components/backtest/
themes_history.json for the bottom of the Backtest tab. Nothing is deployed
and nothing is written to AWS. Zero tokens:

    python3 scripts/themes_history_report.py --from 2025-10     # last year
    python3 scripts/themes_history_report.py --from 2020-01     # back to 2020

What this is, and is not:
  * The detector is deterministic (RS vs SPY, 200d EMA trend, onset = start of the
    current run, with dips under 15 calendar days merged into it), so each date can be
    recomputed exactly with the data available on that date.
  * It uses TODAY's theme legs (extended 2026-10-09), so it is a reconstruction,
    not a stored copy of what CGI showed on those dates.
  * The stage cut-offs (55 / 152 days) and the megatrend rule (> 365 days) were
    measured on the full history, so older snapshots are slightly flattered by
    hindsight.
  * Prices are loaded from LOAD_FROM, not from 1993, so a run's age is capped by
    how far back that goes (~4 years before the earliest snapshot).
"""
from __future__ import annotations

import argparse
import calendar
import concurrent.futures as cf
import datetime as dt
import json
import sys
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
import axis_drivers as ad  # noqa: E402
import regime_matrix as rm  # noqa: E402
import themes_data as td  # noqa: E402

LOAD_FROM = "2016-01-01"
OUT = ROOT / "web" / "app" / "components" / "backtest" / "themes_history.json"
OUT_COUNTRIES = ROOT / "web" / "app" / "components" / "countries" / "countries_history.json"


def load_since(sym: str, since: str) -> dict[str, float]:
    ddb = boto3.client("dynamodb", region_name=ad.REGION)
    kw = dict(
        TableName=ad.PRICE_TABLE,
        KeyConditionExpression="#s = :s AND #d >= :f",
        ExpressionAttributeNames={"#s": "symbol", "#d": "date", "#c": "close"},
        ExpressionAttributeValues={":s": {"S": sym}, ":f": {"S": since}},
        ProjectionExpression="#d, #c",
    )
    out: dict[str, float] = {}
    while True:
        page = ddb.query(**kw)
        for it in page["Items"]:
            if "close" in it and "N" in it["close"]:
                v = float(it["close"]["N"])
                if v:  # same rule as themes_data._load: a zero close is a bad bar, not a price
                    out[it["date"]["S"]] = v
        if "LastEvaluatedKey" not in page:
            return out
        kw["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def snapshot(T: str, bench_all: dict[str, float], px_all: dict[str, dict[str, float]]) -> list[list]:
    bench = {d: v for d, v in bench_all.items() if d <= T}
    rows = []
    for theme, syms in td.THEMES.items():
        running, n_legs = [], 0
        for s in syms:
            p = px_all.get(s) or {}
            p = {d: v for d, v in p.items() if d <= T}
            if not p:
                continue
            r = td._run(p, bench)
            if r.get("status") in ("running", "no active run"):
                n_legs += 1                      # same rule as n_legs in themes_data.build_themes_response
            if r.get("status") == "running":
                running.append({"symbol": s, **r})
        if not running:
            continue
        lead = min(running, key=lambda l: l["onset"])
        age = lead["age_days"]
        rows.append([theme, td._stage(age), "megatrend" if age > td.MEGATREND_DAYS else "rotation",
                     age, lead["symbol"], lead["onset"], len(running), n_legs])
    rows.sort(key=lambda t: (t[2] != "megatrend", t[3]))
    return rows


def snapshot_countries(T: str, bench_all: dict[str, float], px_all: dict[str, dict[str, float]]) -> list[list]:
    """Same rule as api/country_data._countries_in_force, replayed as of T: a country is in force while any of its ETFs is in
    a run; its age is the oldest running ETF's."""
    bench = {d: v for d, v in bench_all.items() if d <= T}
    rows = []
    for c in rm.COUNTRIES:
        running, n_etfs = [], 0
        for s in c["etfs"]:
            p = {d: v for d, v in (px_all.get(s) or {}).items() if d <= T}
            if not p:
                continue
            r = td._run(p, bench)
            if r.get("status") in ("running", "no active run"):
                n_etfs += 1
            if r.get("status") == "running":
                running.append({"symbol": s, **r})
        if not running:
            continue
        lead = min(running, key=lambda x: x["onset"])
        age = lead["age_days"]
        rows.append([c["name"], td._stage(age), "megatrend" if age > td.MEGATREND_DAYS else "rotation",
                     age, lead["symbol"], lead["onset"], len(running), n_etfs])
    rows.sort(key=lambda t: (t[2] != "megatrend", t[3]))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", required=True, help="first month, YYYY-MM")
    a = ap.parse_args()

    syms = sorted({td.BENCH, *[s for ss in td.THEMES.values() for s in ss], *[e for c in rm.COUNTRIES for e in c["etfs"]]})
    print(f"loading {len(syms)} symbols from {LOAD_FROM} ...", flush=True)
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        loaded = dict(zip(syms, ex.map(lambda s: load_since(s, LOAD_FROM), syms)))
    bench = loaded[td.BENCH]
    dates = sorted(bench)

    y, m = int(a.start[:4]), int(a.start[5:])
    ends = []
    while (y, m) <= (int(dates[-1][:4]), int(dates[-1][5:7])):
        me = f"{y}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"
        ends.append(max(d for d in dates if d <= me))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    ends = sorted(set(ends))
    if dates[-1] not in ends:
        ends.append(dates[-1])

    snaps, csnaps = [], []
    for T in ends:
        snaps.append({"d": T, "t": snapshot(T, bench, loaded)})
        csnaps.append({"d": T, "t": snapshot_countries(T, bench, loaded)})
        print(T, len(snaps[-1]["t"]), "themes in force;", len(csnaps[-1]["t"]), "countries in force", flush=True)

    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "load_from": LOAD_FROM,
        "first_snapshot": ends[0],
        "latest_bar": dates[-1],
        "cols": ["theme", "stage", "class", "age_days", "lead", "onset", "n_running", "n_legs"],
        "snapshots": snaps,
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    cout = {**{k: v for k, v in out.items() if k not in ("cols", "snapshots")},
            "cols": ["country", "stage", "class", "age_days", "lead", "onset", "n_running", "n_etfs"], "snapshots": csnaps}
    OUT_COUNTRIES.parent.mkdir(parents=True, exist_ok=True)
    OUT_COUNTRIES.write_text(json.dumps(cout, separators=(",", ":")))
    print(f"wrote {OUT_COUNTRIES.relative_to(ROOT)} ({OUT_COUNTRIES.stat().st_size // 1024} KB)")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB, {len(snaps)} snapshots)")


if __name__ == "__main__":
    main()
