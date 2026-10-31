"""Offline checks for freshness.gdp_problems (the GDP-store check) and for the backend release schedule.

Run: api/.venv/bin/python scripts/check_gdp_check.py
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


D = dt.date.fromisoformat
check("today's state: 29 Oct release, newest stored 30 Sep -> 1 problem", fr.gdp_problems(D("2026-11-01"), "2026-09-30")["n_problems"], 1)
check("fixed: row stored for 29 Oct -> clean", fr.gdp_problems(D("2026-11-01"), "2026-10-29")["n_problems"], 0)
check("release day + 1 is inside the 2-day allowance", fr.gdp_problems(D("2026-10-30"), "2026-09-30")["n_problems"], 0)
check("two days after the release it is a problem", fr.gdp_problems(D("2026-10-31"), "2026-09-30")["n_problems"], 1)
check("calendar a day off a shifted BEA date is tolerated (stored 26 Aug, calendar 27 Aug)", fr.gdp_problems(D("2026-09-02"), "2026-08-26")["n_problems"], 0)
check("empty table", fr.gdp_problems(D("2026-11-01"), None)["n_problems"], 1)
check("custom releases list", fr.gdp_problems(D("2027-02-01"), "2026-12-23", [{"type": "GDP", "date": "2027-01-28"}])["n_problems"], 1)

# the backend updater's own schedule (cmon-backend-service/src/external_api/gdp_release.py) must agree with this calendar from 2026-10-29 on
path = os.path.expanduser("~/cmon-backend-service/src/external_api")
if os.path.isdir(path):
    sys.path.insert(0, path)
    import gdp_release as g  # noqa: E402

    ours = sorted(r["date"] for r in rc.RELEASES if r["type"] == "GDP" and r["date"] >= "2026-10-29")
    check("backend BEA schedule == release_calendar GDP dates from 2026-10-29", sorted(g.BEA_RELEASES), ours)
else:
    print("skip backend schedule comparison (repo not found)")

print("FAILS:", fails)
sys.exit(1 if fails else 0)
