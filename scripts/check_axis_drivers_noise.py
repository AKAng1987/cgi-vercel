"""Checks for the driver-table noise flag (axis_drivers.wilson / is_noise).

Run: api/.venv/bin/python scripts/check_axis_drivers_noise.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
import axis_drivers as A  # noqa: E402

fails = 0


def check(name, got, want):
    global fails
    ok = got == want
    fails += 0 if ok else 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  got={got!r} want={want!r}"))


lo, hi = A.wilson(0.5, 100)
check("wilson(0.5, 100) 95% is about [0.404, 0.596]", (round(lo, 3), round(hi, 3)), (0.404, 0.596))
lo, hi = A.wilson(0.0, 20)
check("wilson never below 0 and has an upper bound at p=0", (round(lo, 3) >= 0.0, 0.1 < hi < 0.2), (True, True))
check("n=0 is the whole range", A.wilson(0.3, 0), (0.0, 1.0))
check("the 57% core capex cell (35 windows) vs base 43%: noise", A.is_noise(0.571, 35, 0.427), True)
check("90 of 100 vs base 40%: not noise", A.is_noise(0.9, 100, 0.4), False)
check("6 windows at 50% vs base 40%: noise (too thin to say)", A.is_noise(0.5, 6, 0.4), True)
check("no cell rate: None", A.is_noise(None, 35, 0.4), None)
check("no windows: None", A.is_noise(0.5, 0, 0.4), None)
sys.exit(1 if fails else 0)
