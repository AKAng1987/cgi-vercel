"""
How long do regimes last?

Descriptive history over the same model-history rows the Markov layer reads
(DynamoDB, the live source), so it moves whenever a regime event is written and
needs no refresh job of its own.

Three levels, because they answer different questions:
  compass    liquidity x credit quadrant (C1-C4)
  grid       growth x inflation quadrant (G1-G4)
  combined   the C x G regime -- changes when EITHER axis pair changes

Only COMPLETED runs enter the statistics. The run in force is reported
separately with its age, because an open run is censored: counting its age so
far as a duration would drag every mean down. `survival_pct` is the share of
completed runs of the same kind that lasted longer than the current age -- the
same definition the themes use. A base rate, not a forecast.

Rules this module holds to:
1. n travels with every number; n < 10 is flagged thin, n <= 4 anecdotal.
2. No thresholds or regime rules are touched. This reads history only.
3. Pure functions over (date, quadrant) rows, so the arithmetic is testable
   without AWS.
"""
from __future__ import annotations

import datetime as dt
import statistics
from typing import Optional

SCHEMA_VERSION = 1

THIN_N = 10
ANECDOTAL_N = 4

CAVEAT = (
    "Descriptive history, not a forecast. Completed runs only; the run in force is "
    "shown separately because its age is censored. Rows with n<10 are thin and n<=4 "
    "anecdotal. Regimes here are in-sample over the model history."
)


def _days(a: str, b: str) -> int:
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def _collapse(events: list[tuple[str, object]], today: str) -> list[dict]:
    """(date, key) events -> runs. A run ends at the next date the key CHANGES;
    consecutive events with the same key are one run. The last run is open."""
    runs: list[dict] = []
    for d, k in events:
        if runs and runs[-1]["key"] == k:
            continue
        if runs:
            runs[-1]["end"] = d
        runs.append({"key": k, "start": d, "end": None})
    for r in runs:
        r["open"] = r["end"] is None
        r["days"] = _days(r["start"], r["end"] if r["end"] else today)
    return runs


def axis_runs(rows: list[tuple[str, int]], today: str) -> list[dict]:
    # One value per date (last wins), matching how the rest of CGI keys events.
    return _collapse(sorted(dict(rows).items()), today)


def combined_runs(compass_rows: list[tuple[str, int]], grid_rows: list[tuple[str, int]], today: str) -> list[dict]:
    cm, gm = dict(compass_rows), dict(grid_rows)
    cq = gq = None
    events: list[tuple[str, str]] = []
    for d in sorted(set(cm) | set(gm)):
        cq = cm.get(d, cq)
        gq = gm.get(d, gq)
        if cq is None or gq is None:
            continue
        events.append((d, f"C{cq}G{gq}"))
    return _collapse(events, today)


def _stats(days: list[int]) -> dict:
    n = len(days)
    if n == 0:
        return {"n": 0, "thin": True, "anecdotal": True}
    return {
        "n": n,
        "mean_days": round(statistics.mean(days)),
        "median_days": round(statistics.median(days)),
        "min_days": min(days),
        "max_days": max(days),
        "thin": n < THIN_N,
        "anecdotal": n <= ANECDOTAL_N,
    }


def _by_key(runs: list[dict]) -> dict:
    done = [r for r in runs if not r["open"]]
    keys = sorted({r["key"] for r in done}, key=str)
    return {str(k): _stats([r["days"] for r in done if r["key"] == k]) for k in keys}


def _current(runs: list[dict]) -> Optional[dict]:
    if not runs or not runs[-1]["open"]:
        return None
    cur = runs[-1]
    same = [r["days"] for r in runs if not r["open"] and r["key"] == cur["key"]]
    allr = [r["days"] for r in runs if not r["open"]]
    out = {
        "regime": str(cur["key"]),
        "since": cur["start"],
        "age_days": cur["days"],
        "completed_runs_of_this_regime": len(same),
        "survival_pct_same_regime": (
            round(100 * sum(1 for d in same if d > cur["days"]) / len(same)) if same else None
        ),
        "survival_pct_any_regime": (
            round(100 * sum(1 for d in allr if d > cur["days"]) / len(allr)) if allr else None
        ),
    }
    if same:
        out["same_regime_median_days"] = round(statistics.median(same))
    return out


def compute(compass_rows: list[tuple[str, int]], grid_rows: list[tuple[str, int]], today: str) -> dict:
    cr = axis_runs(compass_rows, today)
    gr = axis_runs(grid_rows, today)
    mr = combined_runs(compass_rows, grid_rows, today)

    def level(runs: list[dict]) -> dict:
        done = [r["days"] for r in runs if not r["open"]]
        return {"overall": _stats(done), "by_regime": _by_key(runs), "current": _current(runs)}

    return {
        "schema_version": SCHEMA_VERSION,
        "as_of": today,
        "compass": level(cr),
        "grid": level(gr),
        "combined": level(mr),
        "caveat": CAVEAT,
    }


def build_regime_durations_response() -> dict:
    import markov_data  # deferred: pulls boto3/DynamoDB, which the pure functions above must not need

    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    return compute(
        markov_data._load_model("compass_US"),
        markov_data._load_model("grid_US"),
        today,
    )
