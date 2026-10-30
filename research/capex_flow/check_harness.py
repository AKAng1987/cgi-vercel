"""check_harness.py -- (1) group arithmetic on hand-built companies; (2) the walk-forward must FIND a planted capex->revenue effect
and must NOT find one in noise (repo standard: >= 6/8 found, <= 2/20 false)."""
import datetime as dt
import numpy as np
import flow_study as F

# ── 1. unit checks ──────────────────────────────────────────────────────────
def co(t, rq, rf):
    return {"t": t, "rq1": rq, "rfiled1": rf, "cq1": {}, "filed1": {}}

A = co("A", {"2024Q1": 100.0, "2025Q1": 130.0}, {"2024Q1": "2024-05-01", "2025Q1": "2025-05-02"})
B = co("B", {"2024Q1": 100.0, "2025Q1": 110.0}, {"2024Q1": "2024-05-03", "2025Q1": "2025-05-10"})
g, known, n = F.group_growth([A, B], "2025Q1", "rq1", "rfiled1")
assert abs(g - 20.0) < 1e-9 and known == "2025-05-10" and n == 2, (g, known, n)      # (240/200 - 1), knowable when the LATER filed
g, known, n = F.group_growth([A, B, co("C", {}, {})], "2025Q1", "rq1", "rfiled1")
assert g is None and n == 2, "2 of 3 members is under the 75% floor"
g, known, n = F.group_growth([A, B, co("C", {}, {}), co("D", {}, {})], "2025Q1", "rq1", "rfiled1", min_share=0.5)
assert abs(g - 20.0) < 1e-9 and n == 2
assert F.q_shift("2025Q1", -4) == "2024Q1" and F.q_range("2025Q4", "2026Q2") == ["2025Q4", "2026Q1", "2026Q2"]

rows = [{"q": "2024Q1", "r": 5.0, "g": 10.0, "known": "d1"}, {"q": "2024Q2", "r": 6.0, "g": 12.0, "known": "d2"},
        {"q": "2024Q3", "r": 7.0, "g": None, "known": "d3"}, {"q": "2024Q4", "r": 8.0, "g": 14.0, "known": "d4"}]
ex = F.examples(rows)
assert [(e["q"], e["r"], e["g"], e["y"]) for e in ex] == [("2024Q1", 5.0, 10.0, 6.0), ("2024Q2", 6.0, 12.0, 7.0)], ex   # Q3 has no capex figure, Q4 has no next quarter
ex1 = F.examples(rows, lag=1)
assert [(e["q"], e["g"], e["y"]) for e in ex1] == [("2024Q2", 10.0, 7.0), ("2024Q3", 12.0, 8.0)], ex1                 # capex one quarter earlier
# the training filter is by FILING DATE of the target, not by quarter label
base = {"q": "2024Q1", "r": 1.0, "g": 1.0, "y": 2.0, "known": "2024-05-15", "ty_known": "2024-08-15"}
late = {"q": "2024Q2", "r": 2.0, "g": 1.0, "y": 3.0, "known": "2024-08-15", "ty_known": "2024-11-15"}
now_row = {"q": "2024Q3", "r": 3.0, "g": 1.0, "y": 4.0, "known": "2024-10-01", "ty_known": "2025-02-01"}
# at 2024-10-01: base's target was filed 2024-08-15 (on file); late's target is filed 2024-11-15 (NOT yet on file)
tr = [e for e in [base, late] if e.get("ty_known") and e["ty_known"] <= now_row["known"]]
assert tr == [base], tr
print("unit checks ok")


# ── 2. planted effect ───────────────────────────────────────────────────────
def synth(effect=0.0, seed=0, n=60):
    rng = np.random.default_rng(seed)
    qs = F.q_range("2012Q1", F.q_shift("2012Q1", n - 1))
    g = rng.normal(0, 10, n)
    r = np.zeros(n)
    for i in range(1, n):
        r[i] = 0.5 * r[i - 1] + effect * g[i - 1] + rng.normal(0, 3)
    def iso(q, add):
        y, k = int(q[:4]), int(q[5])
        d = dt.date(y, k * 3, 28) + dt.timedelta(days=add)
        return d.isoformat()
    # information date = 45 days after the quarter ends; the group's own revenue for the quarter is on file by then
    return [{"q": q, "r": float(r[i]), "g": float(g[i]), "known": iso(q, 45), "rknown": iso(q, 45)} for i, q in enumerate(qs)]


def claim(rows):
    r = F.compare(rows)
    return bool(r.get("helps"))


if __name__ == "__main__":
    found = sum(claim(synth(effect=0.5, seed=s)) for s in range(8))
    false = sum(claim(synth(effect=0.0, seed=100 + s)) for s in range(20))
    weak = sum(claim(synth(effect=0.15, seed=300 + s)) for s in range(8))
    real = sum(claim(synth(effect=0.3, seed=400 + s, n=30)) for s in range(20))
    print(f"(detectable size: at the REAL sample (about 30 quarters, 14 scored), an effect of 0.3 per point of capex growth is found {real}/20 times)")
    print(f"(power note: a MODERATE planted effect, 0.15 of the capex swing, is found {weak}/8 at 60 quarters)")
    print(f"strong planted capex -> revenue effect found: {found}/8")
    print(f"noise: capex falsely claimed to help {false}/20")
    ok = found >= 6 and false <= 2
    print("SELFTEST", "OK" if ok else "FAILED")
    raise SystemExit(0 if ok else 1)
