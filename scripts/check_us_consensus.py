"""Offline checks for api/us_consensus.py (classify, parse, merge-upsert, implied flip).

Run: api/.venv/bin/python scripts/check_us_consensus.py
"""
from __future__ import annotations

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
import us_consensus as uc  # noqa: E402

fails = 0


def check(name, got, want):
    global fails
    ok = got == want
    fails += 0 if ok else 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  got={got!r} want={want!r}"))


T = dt.date(2026, 10, 30)
check("GDP QoQ Adv", uc.classify("GDP Growth Rate", "GDP Growth Rate QoQ Adv"), "gdp")
check("GDP YoY is not used", uc.classify("GDP Annual Growth Rate", "GDP Growth Rate YoY Adv"), None)
check("CPI YoY", uc.classify("Inflation Rate", "Inflation Rate YoY"), "cpi")
check("core CPI is not used", uc.classify("Core Inflation Rate", "Core Inflation Rate YoY"), None)
check("CPI MoM is not used", uc.classify("Inflation Rate Mom", "Inflation Rate MoM"), None)

rows = [
    ["US", "2026-10-29T12:30:00Z", "GDP Growth Rate QoQ Adv", "GDP Growth Rate", "gdp", "Q3", 2.2, 3.2, 0, "ECONOMICS:USGDPQQ", 3.4],
    ["US", "2026-11-10T13:30:00Z", "Inflation Rate YoY", "Inflation Rate", "prices", "Oct", 3.0, 3.2, 1, None],       # 10 fields: no actual
    ["US", "2026-11-10T13:30:00Z", "Core Inflation Rate YoY", "Core Inflation Rate", "prices", "Oct", 3.0, 3.0, 1, None],
    ["PH", "2026-11-05T00:00:00Z", "Inflation Rate YoY", "Inflation Rate", "prices", "Oct", 1, 1, 0, None],
    ["US", "2024-01-01", "GDP Growth Rate QoQ Adv", "GDP Growth Rate", "gdp", "Q4", 1, 1, 0, None],                    # far outside the window
    "garbage",
]
new, rep = uc.parse(rows, T)
check("keeps the two US GDP/CPI rows", [(r["kind"], r["date"]) for r in new], [("gdp", "2026-10-29"), ("cpi", "2026-11-10")])
check("actual taken from the 11th field, None when absent", [r["actual"] for r in new], [3.4, None])
check("report counts what was dropped", (rep["received"], rep["kept"], rep["dropped"]), (4, 2, {"not gdp/cpi": 1, "outside window": 1}))

# upsert: a later post fills the actual and never erases a forecast
old = [{"date": "2026-10-29", "kind": "gdp", "title": "GDP Growth Rate QoQ Adv", "period": "Q3", "previous": 2.2, "forecast": 3.2, "actual": None}]
later = [{"date": "2026-10-29", "kind": "gdp", "title": "GDP Growth Rate QoQ Adv", "period": "Q3", "previous": 2.2, "forecast": None, "actual": 3.4}]
m = uc.merge(old, later)
check("one row, forecast kept, actual filled", (len(m), m[0]["forecast"], m[0]["actual"]), (1, 3.2, 3.4))
check("a new release is added", len(uc.merge(m, new)), 2)
many = [{"date": f"2020-{(i % 12) + 1:02d}-{(i % 27) + 1:02d}", "kind": "cpi", "title": f"t{i}"} for i in range(500)]
check("history is capped", len(uc.merge([], many)), uc.MAX_KEEP)

# implied flip: axis up needs the new print BELOW previous; down needs it ABOVE
snap = {"at": "2026-10-29T10:00:00+00:00", "rows": [
    {"date": "2026-10-29", "kind": "gdp", "title": "x", "forecast": 3.2, "previous": 2.2, "actual": None},
    {"date": "2026-11-10", "kind": "cpi", "title": "x", "forecast": 3.0, "previous": 3.2, "actual": None},
    {"date": "2026-12-01", "kind": "gdp", "title": "x", "forecast": 2.0, "previous": 2.0, "actual": None}]}
check("up, forecast above previous: no flip", uc.implied("gdp", "2026-10-29", 1, snap)["implied_flip"], False)
check("down, forecast above previous: flip", uc.implied("gdp", "2026-10-29", 0, snap)["implied_flip"], True)
check("up, CPI forecast below previous: flip", uc.implied("cpi", "2026-11-10", 1, snap)["implied_flip"], True)
check("gap sign: up axis, forecast 3.2 vs 2.2 = -1.0", uc.implied("gdp", "2026-10-29", 1, snap)["gap"], -1.0)
t = uc.implied("gdp", "2026-12-01", 1, snap)
check("tie is no flip and says so", (t["implied_flip"], t["tie"]), (False, True))
check("a row 4 days from the release is not matched", uc.implied("gdp", "2026-11-04", 1, snap), None)
check("no forecast: None", uc.implied("gdp", "2026-10-29", 1, {"rows": [{"date": "2026-10-29", "kind": "gdp", "forecast": None, "previous": 2.0}]}), None)
check("wrong kind: None", uc.implied("cpi", "2026-10-29", 1, snap), None)
import release_calendar as rc  # noqa: E402

# the routine refetches while a consensus is outstanding
rel = rc.RELEASES
check("CPI on 10 Nov, no forecast stored, 8 Nov: outstanding", uc.missing_forecasts(dt.date(2026, 11, 8), {"rows": []}, rel), ["2026-11-10"])
check("same, with a forecast stored: none", uc.missing_forecasts(dt.date(2026, 11, 8), {"rows": [
    {"date": "2026-11-10", "kind": "cpi", "forecast": 3.6, "previous": 3.7}]}, rel), [])
check("a forecast with no previous does not count", uc.missing_forecasts(dt.date(2026, 11, 8), {"rows": [
    {"date": "2026-11-10", "kind": "cpi", "forecast": 3.6, "previous": None}]}, rel), ["2026-11-10"])
check("11 days ahead: not outstanding yet", uc.missing_forecasts(dt.date(2026, 10, 30), {"rows": []}, rel), [])
check("GDP second estimate (25 Nov) never counts", [d for d in uc.missing_forecasts(dt.date(2026, 11, 23), {"rows": []}, rel)], [])
check("GDP advance counts (28 Jan 2027)", uc.missing_forecasts(dt.date(2027, 1, 26), {"rows": []}, rel), ["2027-01-27", "2027-01-28"][1:])
sys.exit(1 if fails else 0)
