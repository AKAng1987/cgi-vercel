"""Offline checks for the capex view: year-to-date differencing, quarter keys, contribution maths.

Run: api/.venv/bin/python scripts/check_capex.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

import capex_data as cd  # noqa: E402
import sec_xbrl as sx  # noqa: E402

fails = 0


def check(name, got, want):
    global fails
    ok = got == want
    fails += 0 if ok else 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  got={got!r} want={want!r}"))


def row(start, end, val, filed):
    return {"start": start, "end": end, "val": val, "filed": filed}


def facts_for(tag, rows):
    return {"facts": {"us-gaap": {tag: {"units": {"USD": rows}}}}}


# 1. year-to-date differencing, calendar year: Q1 3m, Q2 6m, Q3 9m, FY 12m (no Q4 tagged)
T = "PaymentsToAcquirePropertyPlantAndEquipment"
f = facts_for(T, [
    row("2025-01-01", "2025-03-31", 10e9, "2025-04-30"),
    row("2025-01-01", "2025-06-30", 25e9, "2025-07-30"),
    row("2025-01-01", "2025-09-30", 45e9, "2025-10-30"),
    row("2025-01-01", "2025-12-31", 70e9, "2026-02-01"),
])
q = sx.cash_quarters(f, ("capex",))
check("Q1 is the three-month window", q["2025-03-31"][0], 10e9)
check("Q2 = 6m - 3m", q["2025-06-30"][0], 15e9)
check("Q3 = 9m - 6m", q["2025-09-30"][0], 20e9)
check("Q4 = 12m - 9m", q["2025-12-31"][0], 25e9)
check("Q4 filed date is the later of its two windows", q["2025-12-31"][1], "2026-02-01")

# 2. a restatement: the later-filed value wins
f = facts_for(T, [
    row("2025-01-01", "2025-03-31", 10e9, "2025-04-30"),
    row("2025-01-01", "2025-03-31", 11e9, "2026-04-30"),
])
check("restated value wins", sx.cash_quarters(f, ("capex",))["2025-03-31"][0], 11e9)

# 3. a missing middle window leaves the quarter out rather than guessing it
f = facts_for(T, [
    row("2025-01-01", "2025-03-31", 10e9, "2025-04-30"),
    row("2025-01-01", "2025-09-30", 45e9, "2025-10-30"),
])
q = sx.cash_quarters(f, ("capex",))
check("no 6m window: Q2 absent", "2025-06-30" in q, False)
check("no 6m window: Q3 absent", "2025-09-30" in q, False)

# 4. tag chain: an alternate tag fills periods the first tag does not cover
f = {"facts": {"us-gaap": {
    "PaymentsToAcquireProductiveAssets": {"units": {"USD": [row("2025-01-01", "2025-03-31", 7e9, "2025-04-30")]}},
}}}
check("alt tag read", sx.cash_quarters(f, ("capex", "capex_alt"))["2025-03-31"][0], 7e9)

# 5. fiscal year not on the calendar (Jul-Jun): windows share the start date
f = facts_for(T, [
    row("2025-07-01", "2025-09-30", 4e9, "2025-10-25"),
    row("2025-07-01", "2025-12-31", 10e9, "2026-01-25"),
])
q = sx.cash_quarters(f, ("capex",))
check("off-calendar Q2 = 6m - 3m", q["2025-12-31"][0], 6e9)

# 6. calendar-quarter keys
check("NVDA-style 26 Jul -> Q2", cd.cal_quarter("2026-07-26"), "2026Q2")
check("31 Jan -> prior Q4", cd.cal_quarter("2026-01-31"), "2025Q4")
check("30 Apr -> Q1", cd.cal_quarter("2026-04-30"), "2026Q1")
check("3 Jan 52-week -> prior Q4", cd.cal_quarter("2026-01-03"), "2025Q4")
check("quarter shift back 4", cd.q_shift("2026Q2", -4), "2025Q2")
check("quarter shift across year", cd.q_shift("2025Q1", -1), "2024Q4")
check("range", cd.q_range("2025Q4", "2026Q2"), ["2025Q4", "2026Q1", "2026Q2"])

# 7. contributions: sectors add to total, matched sample only
comps = [
    {"t": "A", "sector": "Information Technology", "cq": {"2025Q2": 100.0, "2026Q2": 160.0}},
    {"t": "B", "sector": "Communication Services", "cq": {"2025Q2": 200.0, "2026Q2": 300.0}},
    {"t": "C", "sector": "Utilities", "cq": {"2025Q2": 100.0, "2026Q2": 90.0}},
    {"t": "D", "sector": "Energy", "cq": {"2025Q2": 100.0}},                 # not filed yet
    {"t": "E", "sector": "Financials", "cq": {"2026Q2": 50.0}},              # no prior year: out
]
r = cd.contributions(comps, ["2026Q2"])[0]
check("matched base 400, delta 150 -> total 37.5", r["total_yoy_pct"], 37.5)
check("IT contribution 60/400", r["contrib"]["Information Technology"], 15.0)
check("Comm contribution 100/400", r["contrib"]["Communication Services"], 25.0)
check("Utilities contribution -10/400", r["contrib"]["Utilities"], -2.5)
check("sectors sum to total", round(sum(r["contrib"].values()), 2), r["total_yoy_pct"])
check("coverage = matched / all prior (400/500)", r["coverage"], 0.8)
check("coverage under 90% is partial", r["partial"], True)
check("matched count", (r["n_matched"], r["n_prior"]), (3, 4))
comps.pop(3)
check("all reported is not partial", cd.contributions(comps, ["2026Q2"])[0]["partial"], False)
check("no prior year -> no number", cd.contributions(comps, ["2025Q2"])[0]["total_yoy_pct"], None)

# 8. spenders: TTM needs four consecutive quarters; outspending flag; top-5 share
def co(t, per_q, ocf):
    return {"t": t, "name": t, "sector": "Utilities",
            "cq": {"2025Q3": per_q, "2025Q4": per_q, "2026Q1": per_q, "2026Q2": per_q, "2025Q2": per_q},
            "ocf_ttm": ocf, "rev_ttm": 1000.0}


s = cd.spenders([co("X", 100.0, 300.0), co("Y", 50.0, 300.0),
                 {"t": "Z", "name": "Z", "sector": "Utilities", "cq": {"2026Q2": 10.0}, "ocf_ttm": 1.0, "rev_ttm": 1.0}])
check("ttm needs four quarters (Z dropped)", s["n_with_ttm"], 2)
check("top is X, ttm 400m -> 0.4b", (s["top"][0]["ticker"], s["top"][0]["capex_ttm_b"]), ("X", 0.4))
check("X spends more than it generates (400 > 300)", s["top"][0]["outspends_cash_flow"], True)
check("Y does not (200 < 300)", s["top"][1]["outspends_cash_flow"], False)
check("capex to ocf", s["top"][0]["capex_to_ocf"], 1.33)
check("yoy needs the same quarter a year earlier", s["top"][0]["yoy_pct"], 0.0)

# 9. a snapshot-less response degrades, never raises
cd.read_snapshot = lambda: None
check("no snapshot -> available False", cd.build_capex_response()["available"], False)

# 10. freshness rule (pure part): expected quarter = latest one whose end is 75+ days past
import datetime as dt  # noqa: E402
import freshness as fr  # noqa: E402

snap = {"built_at": "2026-10-20T00:00:00+00:00", "n_universe": 10, "failed": [],
        "companies": [{"t": str(i), "cq": {"2026Q2": 1.0}} for i in range(10)]}
r = fr.capex_problems(snap, dt.date(2026, 10, 29))
check("2026Q2 expected on 29 Oct 2026", r["expected_quarter"], "2026Q2")
check("all have it: no problem", r["n_problems"], 0)
r = fr.capex_problems(snap, dt.date(2026, 12, 20))
check("2026Q3 expected after 14 Dec, snapshot lacks it -> behind", "behind" in [p["check"] for p in r["problems"]], True)
check("9 days old is fine", fr.capex_problems(snap, dt.date(2026, 10, 29))["n_problems"], 0)
check("10 days old is stale", [p["check"] for p in fr.capex_problems(snap, dt.date(2026, 10, 30))["problems"]], ["stale"])
snap["built_at"] = "2026-05-01T00:00:00+00:00"
r = fr.capex_problems(snap, dt.date(2026, 10, 29))
check("old snapshot -> stale", [p["check"] for p in r["problems"]], ["stale"])
snap["failed"] = ["a", "b"]
check("20% failed -> gaps", "gaps" in [p["check"] for p in fr.capex_problems(snap, dt.date(2026, 10, 29))["problems"]], True)
check("no snapshot -> one problem", fr.capex_problems(None, dt.date(2026, 10, 29))["n_problems"], 1)

# 11. cash_series: year-to-date windows give consecutive quarters; falls back to series() when none are tagged
f = facts_for(T, [
    row("2025-01-01", "2025-03-31", 10e9, "2025-04-30"), row("2025-01-01", "2025-06-30", 25e9, "2025-07-30"),
    row("2025-01-01", "2025-09-30", 45e9, "2025-10-30"), row("2025-01-01", "2025-12-31", 70e9, "2026-02-01"),
])
cs = sx.cash_series(f, "capex")
check("cash_series returns four quarters", sorted(cs.values()), [10e9, 15e9, 20e9, 25e9])
import fundamentals_data as fd  # noqa: E402
check("TTM cash = 70bn for four consecutive quarters", fd._ttm_cash(cs), 70e9)
check("TTM cash refuses a gap (Q1 2024 + three of 2025)", fd._ttm_cash({"2024-03-31": 1.0, "2025-03-31": 2.0, "2025-06-30": 3.0, "2025-09-30": 4.0}), None)
check("TTM cash needs four values", fd._ttm_cash({"2025-03-31": 1.0, "2025-06-30": 3.0}), None)
old = sx.series(f, "capex")
check("series() alone returns just Q1 for cash flow (the bug this replaces)", list(old.values()), [10e9])

# 12. first-reported values and first-filed dates (point-in-time): next year's 10-Q re-files the quarter as a comparative
f = facts_for(T, [
    row("2025-01-01", "2025-03-31", 10e9, "2025-04-30"), row("2025-01-01", "2025-03-31", 11e9, "2026-04-30"),
    row("2025-01-01", "2025-06-30", 25e9, "2025-07-30"), row("2025-01-01", "2025-06-30", 26e9, "2026-07-30"),
])
last, first = sx.cash_quarters(f, ("capex",)), sx.cash_quarters_first(f, ("capex",))
check("latest-filing reader: Q1 restated 11bn filed 2026-04-30", last["2025-03-31"], (11e9, "2026-04-30"))
check("first-filing reader: Q1 10bn filed 2025-04-30", first["2025-03-31"], (10e9, "2025-04-30"))
check("first-filing reader: Q2 = 25 - 10 = 15bn, dated by the later first filing", first["2025-06-30"], (15e9, "2025-07-30"))

sys.exit(1 if fails else 0)
