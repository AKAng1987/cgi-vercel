"""Offline checks for api/rate_path.py (dates, step-path averages, assembly, history comparison).

Run: api/.venv/bin/python scripts/check_rate_path.py
"""
from __future__ import annotations

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
import rate_path as rp  # noqa: E402

fails = 0


def check(name, got, want):
    global fails
    ok = got == want
    fails += 0 if ok else 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  got={got!r} want={want!r}"))


D = dt.date
check("third Wednesday Dec 2026 is the 16th", rp.third_wednesday(2026, 12), D(2026, 12, 16))
check("third Wednesday Mar 2027 is the 17th", rp.third_wednesday(2027, 3), D(2027, 3, 17))
check("third Wednesday Sep 2027 is the 15th", rp.third_wednesday(2027, 9), D(2027, 9, 15))
c = rp.sr3_contracts(D(2026, 10, 30))
check("first contract from 30 Oct 2026: Sep 2026 (its reference quarter runs 16 Sep to 16 Dec)", c[0]["label"], "Sep 2026")
check("12 contracts, ascending", [len(c), [x["start"] for x in c] == sorted(x["start"] for x in c)], [12, True])
check("tickers", [c[0]["ticker"], c[1]["ticker"], c[4]["ticker"]], ["SR3U26.CME", "SR3Z26.CME", "SR3U27.CME"])
check("Sep 2026 reference quarter", (c[0]["start"], c[0]["end"]), ("2026-09-16", "2026-12-16"))
check("Dec 2026 reference quarter", (c[1]["start"], c[1]["end"]), ("2026-12-16", "2027-03-17"))
c2 = rp.sr3_contracts(D(2026, 12, 17))
check("on 17 Dec 2026 the Dec 2026 contract is still live (quarter ends 17 Mar)", c2[0]["label"], "Dec 2026")
check("on 18 Mar 2027 it has ended", rp.sr3_contracts(D(2027, 3, 18))[0]["label"], "Mar 2027")

# step path average: base 4.00, a +25bp meeting on 9 Dec 2026 (effective 10 Dec)
steps = [(D(2026, 12, 9), 4.25)]
check("window entirely before the meeting is the base", rp.path_average(steps, 4.0, D(2026, 11, 1), D(2026, 12, 1)), 4.0)
check("window entirely after is the new rate", rp.path_average(steps, 4.0, D(2026, 12, 20), D(2027, 1, 20)), 4.25)
a = rp.path_average(steps, 4.0, D(2026, 12, 1), D(2026, 12, 21))   # 9 days at 4.00, 11 days at 4.25
check("window across it is time-weighted: (9*4.00 + 11*4.25)/20", round(a, 4), round((9 * 4.0 + 11 * 4.25) / 20, 4))
check("empty window is None", rp.path_average(steps, 4.0, D(2026, 12, 1), D(2026, 12, 1)), None)

probs = {"effr_latest": 4.0, "lower_target": 3.75, "upper_target": 4.0, "probabilities": [
    {"date": "2026-12-09", "available": True, "post_rate": 4.2, "pre_rate": 4.0, "p_hike": 0.8, "p_hold": 0.2, "p_cut": 0.0,
     "most_likely": "Hike 25bp", "ticker": "ZQF27.CBT"},
    {"date": "2027-01-27", "available": True, "post_rate": 4.3, "pre_rate": 4.2, "p_hike": 0.4, "p_hold": 0.6, "p_cut": 0.0,
     "most_likely": "Hold", "ticker": "ZQG27.CBT"},
    {"date": "2027-03-17", "available": False, "reason": "no quote"}]}
quotes = {x["ticker"]: None for x in c}
quotes["SR3Z26.CME"] = 95.80      # 4.20 implied
quotes["SR3H27.CME"] = 95.60      # 4.40
out = rp.assemble(probs, quotes, {"date": "2026-10-29", "value": 4.05}, [], D(2026, 10, 30))
check("meeting step and cumulative bp", [(m["step_bp"], m["cum_bp"]) for m in out["meetings"] if m["available"]], [(20.0, 20.0), (10.0, 30.0)])
check("an unavailable meeting stays in the list", [m["available"] for m in out["meetings"]], [True, True, False])
check("implied SOFR = 100 - price (Sep 2026 has no quote here)", [s["implied_sofr"] for s in out["sr3"][:3]], [None, 4.2, 4.4])
check("missing quotes stay None", out["sr3"][3]["implied_sofr"], None)
check("SOFR - EFFR gap in bp", out["sofr_minus_effr_bp"], 5.0)
check("SOFR-futures peak is the Mar 2027 point at 4.40 (+40bp)", (out["peak_sofr"]["rate"], out["peak_sofr"]["bp_vs_now"]), (4.4, 40.0))
check("fed-funds peak is the Jan 2027 meeting at 4.30 (+30bp)", (out["peak_fed_funds"]["date"], out["peak_fed_funds"]["rate"], out["peak_fed_funds"]["bp_vs_now"]), ("2027-01-27", 4.3, 30.0))
check("SOFR trough is the lowest quote (Dec 2026, 4.20)", (out["trough_sofr"]["rate"], out["trough_sofr"]["date"]), (4.2, "2026-12-16"))
check("no history: nothing moved", out["moved"], {"week": None, "four_weeks": None})
check("Dec 2026 SR3 has no ZQ comparison (the ZQ path ends before its quarter does)", out["sr3"][1]["vs_zq_bp"], None)

hist = [{"date": "2026-10-02", "effr": 4.0, "meetings": [["2026-12-09", 4.30], ["2027-01-27", 4.40]],
         "sr3": [["SR3Z26.CME", 4.35]]},
        {"date": "2026-10-28", "effr": 4.0, "meetings": [["2026-12-09", 4.10]], "sr3": []}]
mv = rp.moved(out, hist, D(2026, 10, 30))
check("4-week change uses the snapshot on or before 2 Oct", mv["four_weeks"]["snapshot_date"], "2026-10-02")
check("Dec meeting moved from 4.30 to 4.20 = -10bp", mv["four_weeks"]["meetings"][0]["change_bp"], -10.0)
check("SOFR Dec 2026 moved from 4.35 to 4.20 = -15bp", mv["four_weeks"]["sr3"][0]["change_bp"], -15.0)
check("1-week uses the 28 Oct snapshot? no: only snapshots on or before 23 Oct count", mv["week"]["snapshot_date"], "2026-10-02")
import freshness as fr  # noqa: E402

check("freshness: 12 quotes and 8 meetings is healthy", fr.rate_path_problems({"n_sr3_quoted": 12, "n_sr3": 12, "meetings": [{"available": True}] * 8})["n_problems"], 0)
check("freshness: 2 of 12 quotes is a problem", [p["check"] for p in fr.rate_path_problems({"n_sr3_quoted": 2, "n_sr3": 12, "meetings": [{"available": True}] * 8})["problems"]], ["sofr_futures"])
check("freshness: no meetings priced is a problem", [p["check"] for p in fr.rate_path_problems({"n_sr3_quoted": 12, "n_sr3": 12, "meetings": []})["problems"]], ["fed_funds_futures"])
check("freshness: no payload is a problem", fr.rate_path_problems(None)["n_problems"], 1)
sys.exit(1 if fails else 0)
