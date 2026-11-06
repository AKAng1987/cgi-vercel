"""Offline checks for api/context_tables.py drawdowns: the open decline, from_here, and the Nasdaq block.
Run: api/.venv/bin/python scripts/check_drawdowns.py   (the last block reads stored prices, read-only)"""
from __future__ import annotations

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import context_tables as C  # noqa: E402

fails = 0


def check(name, got, want):
    global fails
    ok = got == want
    fails += 0 if ok else 1
    print(("ok  " if ok else "FAIL"), name, "" if ok else f"got {got!r} want {want!r}")


def series(points, start="2000-01-03"):
    d0 = dt.date.fromisoformat(start)
    dates = [(d0 + dt.timedelta(days=i)).isoformat() for i in range(len(points))]
    return dates, [float(p) for p in points]


def ramp(a, b, n):
    return [a + (b - a) * i / n for i in range(1, n + 1)]


# 100 -> 89 (-11%) -> 101 (regains), 101 -> 96 (-5%, edge) -> 105, 105 -> 94 (-10.5%) -> 99.5 -> 110 (regain)
pts = [100] + ramp(100, 89, 10) + ramp(89, 101, 10) + ramp(101, 97, 5) + ramp(97, 105, 5) + ramp(105, 94, 10) + ramp(94, 99.5, 5) + ramp(99.5, 110, 5)
dates, vals = series(pts)
eps = C.declines(dates, vals, 5)
check("two declines of 5% or more", [round(e["depth_pct"]) for e in eps], [-11, -10])
check("both closed", [e["recovered"] for e in eps], [True, True])

# An open decline is counted the day it passes the depth, and sits in the deeper bucket as it deepens.
open_pts = pts + ramp(110, 100, 6)               # -9.1% from the high, still falling
d2, v2 = series(open_pts)
e2 = C.declines(d2, v2, 5)
check("open decline counted at -5%", (round(e2[-1]["depth_pct"], 1), e2[-1]["recovered"]), (-9.1, False))
d3, v3 = series(pts + ramp(110, 97, 8))          # -11.8%
check("open decline is a >=10% episode once it passes 10%", len([e for e in C.declines(d3, v3, 10) if abs(e["depth_pct"]) >= 10]), 3)

# from_here: today's open decline is left out; counts come from the closed ones; none when within 5% of the high.
fh = C.from_here(d2, v2, -9.1)
check("from_here floor and n exclude the open decline", (fh["reached_pct"], fh["n"]), (5, 2))
check("went on to -10%: counted the table's way", [(x["level_pct"], x["n"]) for x in fh["deeper"]][0][0], 10)
check("regain days found for the closed ones", fh["n_regained"], 2)
check("no from_here within 5% of the high", C.from_here(d2, v2, -4.0), None)
check("floor follows today's depth", C.from_here(d3, v3, -11.8)["reached_pct"], 10)

# _regain_days
check("regain days: 10 down, back above the peak", C._regain_days(dates, vals, dates[0], 100.0, dates[10]) is not None, True)
check("regain days: not regained", C._regain_days(d2, v2, dates[-1], 110.0, dates[-1]), None)

# Real data (read-only): both blocks build, the SPX keys the page used are still there, Nasdaq has its own.
a = C.drawdowns()
b = C.drawdowns_nasdaq()
check("SPX payload keeps spx and two windows", ("spx" in a["now"], len(a["windows"])), (True, 2))
check("Nasdaq payload: one window, symbol IXIC, no spx key", (len(b["windows"]), b["now"]["symbol"], "spx" in b["now"]), (1, "IXIC", False))
check("Nasdaq history starts in 1971", b["windows"][0]["start"][:4], "1971")
check("QQQ line present with a drawdown", isinstance((b.get("qqq") or {}).get("drawdown_pct"), float), True)
check("drawdown is at or below zero", a["now"]["drawdown_pct"] <= 0 and b["now"]["drawdown_pct"] <= 0, True)

print("FAILS:", fails)
sys.exit(1 if fails else 0)
