"""Offline checks for api/release_calendar.py and the calendar-runs-out freshness rule.

Run: api/.venv/bin/python scripts/check_release_calendar.py
"""
from __future__ import annotations

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

import freshness as fr  # noqa: E402
import release_calendar as rc  # noqa: E402

fails = 0


def check(name, got, want):
    global fails
    ok = got == want
    fails += 0 if ok else 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  got={got!r} want={want!r}"))


by = {}
for r in rc.RELEASES:
    by.setdefault((r["date"][:4], r["type"]), []).append(r["date"])
for y in ("2026", "2027"):
    check(f"{y}: 12 CPI, 12 GDP, 8 FOMC, 4 SLOOS", [len(by[(y, k)]) for k in ("CPI", "GDP", "FOMC", "SLOOS")], [12, 12, 8, 4])
check("every release is a weekday", [r["date"] for r in rc.RELEASES if dt.date.fromisoformat(r["date"]).weekday() >= 5], [])
check("sorted", [r["date"] for r in rc.RELEASES], sorted(r["date"] for r in rc.RELEASES))
check("no duplicate (type, date)", len({(r["type"], r["date"]) for r in rc.RELEASES}), len(rc.RELEASES))
cpi27 = by[("2027", "CPI")]
check("CPI 2027: one per month", sorted(d[5:7] for d in cpi27), [f"{m:02d}" for m in range(1, 13)])
gdp27 = by[("2027", "GDP")]
check("GDP 2027: advance in Jan/Apr/Jul/Oct", [d[5:7] for d in gdp27][::3], ["01", "04", "07", "10"])
check("GDP subtype of 2027-01-28 is advance", [r["subtype"] for r in rc.RELEASES if r["date"] == "2027-01-28"], ["advance"])
fomc = {d for d in by[("2027", "FOMC")]}
mondays = []
for d in by[("2027", "SLOOS")]:
    dd = dt.date.fromisoformat(d)
    mondays.append(dd.weekday())
check("SLOOS 2027 all Mondays", mondays, [0, 0, 0, 0])
check("SLOOS 2027 is the Monday after the Jan/Apr/Jul/Oct FOMC",
      by[("2027", "SLOOS")],
      [(dt.date.fromisoformat(f) + dt.timedelta(days=(7 - dt.date.fromisoformat(f).weekday()) % 7 or 7)).isoformat()
       for f in sorted(fomc) if f[5:7] in ("01", "04", "07", "10")])
check("next releases after Christmas 2026 include all four types", sorted(r["type"] for r in rc.next_releases("2026-12-24")),
      ["CPI", "FOMC", "GDP", "SLOOS"])

# the alarm
check("calendar fine today", fr.calendar_problems(dt.date(2026, 10, 30))["n_problems"], 0)
check("calendar fine at the end of 2027 minus 80 days", fr.calendar_problems(dt.date(2027, 10, 5))["n_problems"], 0)
r = fr.calendar_problems(dt.date(2027, 11, 20))
check("late Nov 2027: only SLOOS has run out (CPI 10 Dec, GDP 22 Dec, FOMC 8 Dec still ahead)",
      sorted(p["check"] for p in r["problems"]), ["SLOOS"])
check("after 22 Dec 2027 everything has run out",
      sorted(p["check"] for p in fr.calendar_problems(dt.date(2027, 12, 23))["problems"]), ["CPI", "FOMC", "GDP", "SLOOS"])
check("a calendar with no GDP at all is a GDP problem",
      [p["check"] for p in fr.calendar_problems(dt.date(2026, 10, 30), [x for x in rc.RELEASES if x["type"] != "GDP"])["problems"]], ["GDP"])
sys.exit(1 if fails else 0)
