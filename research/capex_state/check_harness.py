"""check_harness.py -- (1) the as-known feature code is checked on hand-built companies; (2) the walk-forward must FIND a planted
capex effect and must NOT find one in noise (repo standard: >= 6/8 found, <= 2/20 false)."""
import numpy as np
import capex_study as C
import erp_study as S

# ── 1. feature unit checks (hand-computed) ──────────────────────────────────
def co(t, cq, filed, ocfq=None, ofiled=None):
    return {"t": t, "cq1": cq, "filed1": filed, "ocfq1": ocfq or {}, "ofiled1": ofiled or {}}

A = co("A", {"2024Q1": 100.0, "2025Q1": 150.0, "2025Q2": 120.0, "2024Q2": 100.0},
       {"2024Q1": "2024-05-01", "2024Q2": "2024-08-01", "2025Q1": "2025-05-01", "2025Q2": "2025-08-10"})
B = co("B", {"2024Q1": 100.0, "2025Q1": 100.0, "2024Q2": 100.0, "2025Q2": 50.0},
       {"2024Q1": "2024-05-02", "2024Q2": "2024-08-02", "2025Q1": "2025-05-20", "2025Q2": "2025-09-20"})
g, cov = C.growth_at([A, B], "2025Q1", "2025-05-10")
assert cov == 0.5 and abs(g - 50.0) < 1e-9, ("only A filed by 10 May: growth 50, coverage 100/200", g, cov)
g, cov = C.growth_at([A, B], "2025Q1", "2025-06-01")
assert cov == 1.0 and abs(g - 25.0) < 1e-9, ("both filed: (50+0)/200 = 25", g, cov)
f = C.features_at([A, B], "2025-06-10")
assert f["q"] == "2025Q1" and abs(f["g1"] - 25.0) < 1e-9, f           # 2025Q2 is not 20 days old yet, and not filed
f = C.features_at([A, B], "2025-08-20")
assert f["q"] == "2025Q1", ("2025Q2 has only A filed (coverage 50% < 80%): stay on 2025Q1", f)
f = C.features_at([A, B], "2025-10-05")
assert f["q"] == "2025Q2" and abs(f["g1"] - ((20 - 50) / 200 * 100)) < 1e-9, f  # (A +20, B -50)/200 = -15
assert C.q_shift("2025Q1", -1) == "2024Q4" and C.q_shift("2025Q4", 1) == "2026Q1"
# a filing 3 days before the decision is NOT known (5-day lag)
f = C.features_at([A], "2025-05-04")
assert f["g1"] is None, f
# a company's quarter counts as known on its FIRST filing date, not the date a later filing repeats it
Z = {"t": "Z", "cq": {"2025Q1": 1.0}, "filed": {"2025Q1": "2026-05-01"}, "cq1": {"2025Q1": 1.0, "2024Q1": 1.0},
     "filed1": {"2025Q1": "2025-05-01", "2024Q1": "2024-05-01"}}
g, cov = C.growth_at([Z], "2025Q1", "2025-06-01")
assert g == 0.0 and cov == 1.0, ("first-filing dates are used, so Z is known by 1 June 2025", g, cov)
# the funding gap gates operating cash flow on ITS OWN first-filed date, which can be a year later than capex's
four = ["2024Q1", "2024Q2", "2024Q3", "2024Q4"]
prior = ["2023Q1", "2023Q2", "2023Q3", "2023Q4"]
G = co("G", {**{q: 10.0 for q in four}, **{q: 10.0 for q in prior}}, {**{q: "2025-01-15" for q in four}, **{q: "2024-02-01" for q in prior}},
       {q: 20.0 for q in four}, {**{q: "2025-01-15" for q in four[:3]}, "2024Q4": "2026-02-01"})
C.MIN_GAP_COMPANIES = 1
assert C.features_at([G], "2025-03-01")["gap"] is None, "OCF for 2024Q4 not on file yet: no gap"
assert abs(C.features_at([G], "2026-03-01")["gap"] - 0.5) < 1e-9, "all four OCF quarters filed: 40/80"
C.MIN_GAP_COMPANIES = 150
print("feature checks ok")

# ── 2. planted effect ───────────────────────────────────────────────────────
def synth(effect=0.0, seed=0, n=150):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        b = int(rng.integers(0, 3))
        r = {"month": f"m{i}", "date": str(i), "e": i * 21, "vol20": float(np.exp(rng.normal(-1.8, 0.4))),
             "comp": int(rng.integers(1, 5)), "grid": int(rng.integers(1, 5)), "b_g1": b if i >= 12 else None,
             "b_acc": None, "b_gap": None, "r1": None, "r3": None, "v3": None}
        base = 2.0 * np.log(r["vol20"]) + 0.5 * (r["comp"] == 3)
        r["dd"] = float(base + effect * ((b == 2) - (b == 0)) + rng.normal())
        rows.append(r)
    return rows


def claim(rows):
    se_b, se_c, _ = S.walkforward(rows, "b_g1", "dd", S.H3)
    if len(se_b) < 40:
        return False
    return S.block_boot(se_b - se_c)[1][0] > 0


if __name__ == "__main__":
    found = sum(claim(synth(effect=1.5, seed=s)) for s in range(8))
    false = sum(claim(synth(effect=0.0, seed=100 + s)) for s in range(20))
    weak = sum(claim(synth(effect=0.6, seed=300 + s)) for s in range(8))
    print(f"(power note: a MODERATE planted effect, 0.6 of the noise sd, is found {weak}/8 at n=150 months)")
    print(f"strong planted capex effect found: {found}/8")
    print(f"noise: capex falsely claimed to help {false}/20")
    ok = found >= 6 and false <= 2
    print("SELFTEST", "OK" if ok else "FAILED")
    raise SystemExit(0 if ok else 1)
