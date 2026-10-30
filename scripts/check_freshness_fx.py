"""Checks for the FX freshness rules in api/freshness.py (referee: today's open FX bar is not 'newer').

Run: api/.venv/bin/python scripts/check_freshness_fx.py
"""
from __future__ import annotations

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
import freshness as fr  # noqa: E402

fails = 0


def check(name, got, want):
    global fails
    ok = got == want
    fails += 0 if ok else 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  got={got!r} want={want!r}"))


def run(sym, ours, tv, today):
    return fr.referee_problems({sym: [[d, c] for d, c in tv]}, {sym: ours}, today)


T = dt.date(2026, 10, 30)
px = lambda ds, v=157.8: [(d, v) for d in ds]
# the 30 Oct case: we hold 29 Oct (the last finished day); TradingView has 29 and 30 (open)
r = run("USDJPY", px(["2026-10-28", "2026-10-29"]), px(["2026-10-28", "2026-10-29", "2026-10-30"]), T)
check("holding the last finished FX day against an open today bar is fine", r["n_problems"], 0)
# the 30 Oct morning flag was holding 28 Oct against {29, 30}: one finished day behind plus the open bar. Two finished days behind is a real lag.
r = run("USDJPY", px(["2026-10-26", "2026-10-27"]), px(["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"]), T)
check("two finished days behind is still flagged", [p["check"] for p in r["problems"]], ["referee_behind"])
check("and the message names the newest FINISHED date, not today", r["problems"][0]["detail"].endswith("already has 2026-10-29"), True)
r = run("USDJPY", px(["2026-10-28"]), px(["2026-10-28", "2026-10-29", "2026-10-30"]), T)
check("holding 28 Oct against {29, open 30}: one finished day behind, the normal lag: not flagged (it was, before this fix)", r["n_problems"], 0)
# other kinds keep counting today's bar (the rule is FX-only)
kinds = {s: k for s, (_tv, k) in fr.REFEREE.items()}
eq = next(s for s, k in kinds.items() if k not in ("fx", "fut", "yield"))
r = run(eq, px(["2026-10-27"], 100.0), px(["2026-10-27", "2026-10-29", "2026-10-30"], 100.0), T)
check(f"{eq} ({kinds[eq]}): today's bar still counts", [p["check"] for p in r["problems"]], ["referee_behind"])
# a wrong close is still caught
r = run("USDJPY", [("2026-10-29", 150.0)], [("2026-10-29", 157.8)], T)
check("a close 5% off is flagged", [p["check"] for p in r["problems"]], ["referee_mismatch"])
sys.exit(1 if fails else 0)
