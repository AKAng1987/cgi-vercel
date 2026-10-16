"""
check_earnings_ledger.py -- offline checks for scripts/earnings_ledger.py (no network, temp store).

Guards: a fact without an sec.gov source or a numeric value is refused (the published page is public and every figure
must be traceable); delta compares the latest quarter with the one before; a claim is judged held / did not hold /
flat from the NEW figure against the baseline recorded when the claim was made; an untestable claim never counts
toward the held score.
"""
import json, pathlib, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import earnings_ledger as el  # noqa: E402

el.STORE = pathlib.Path(tempfile.mkdtemp()) / "facts.json"
SRC = "https://www.sec.gov/Archives/edgar/data/1/2/x.htm"
fail = []


def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        fail.append(name)


def fact(q, v, src=SRC):
    return {"ticker": "JPM", "quarter": q, "source": src, "metrics": {"provision_bn": {"value": v, "unit": "$bn"}}}


check("refuses non-SEC source", el.add([fact("2026Q2", 3.0, "https://example.com/x")]) == 1)
check("refuses non-numeric value", el.add([fact("2026Q2", "3")]) == 1)
check("refuses bad quarter", el.add([fact("Q2-2026", 3.0)]) == 1)
check("stores two quarters", el.add([fact("2026Q2", 3.0), fact("2026Q3", 4.0)]) == 0)
d = el.delta_rows(el.load())
check("delta is Q3 vs Q2, +33.3%", len(d) == 1 and d[0]["from_q"] == "2026Q2" and d[0]["change_pct"] == 33.3)
check("judge up held", el.judge(4.0, 4.5, "up") == "held")
check("judge up fails when it fell", el.judge(4.0, 3.5, "up") == "did not hold")
check("judge flat inside 1%", el.judge(4.0, 4.02, "up") == "flat")
check("judge down held", el.judge(4.0, 3.0, "down") == "held")
el.claim({"id": "c1", "date": "2026-10-18", "thread": "banks", "claim": "provisions up", "ticker": "JPM",
          "metric": "provision_bn", "baseline": 4.0, "direction": "up", "check_quarter": "2026Q4"})
el.claim({"id": "c2", "date": "2026-10-18", "thread": "banks", "claim": "tone is cautious"})
el.score(el.load())
check("claim waits until its quarter exists", el.load()["claims"][0]["result"] is None)
el.add([fact("2026Q4", 4.6)])
el.score(el.load())
db = el.load()
check("claim scored held once Q4 exists", db["claims"][0]["result"] == "held")
check("view claim is not testable", db["claims"][1]["result"] == "not testable")
s = el.summary(db)
check("scorecard counts only tested claims", s["tested"] == 1 and s["held"] == 1 and s["not_testable"] == 1)
sys.exit(1 if fail else 0)
