"""check_harness.py -- the method must FIND a planted ERP effect and must NOT find one in noise (repo standard: >= 6/8, <= 2/20)."""
import numpy as np
import erp_study as S


def synth(effect=0.0, seed=0, n=200):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        b = int(rng.integers(0, 3))
        r = {"month": f"m{i}", "date": str(i), "e": i * 21, "vol20": float(np.exp(rng.normal(-1.8, 0.4))),
             "comp": int(rng.integers(1, 5)), "grid": int(rng.integers(1, 5)), "b_level": b if i >= 12 else None,
             "b_chg": None, "b_gap": None, "r1": None, "r3": None, "v3": None}
        base = 2.0 * np.log(r["vol20"]) + 0.5 * (r["comp"] == 3)
        r["dd"] = float(base + effect * ((b == 0) - (b == 2)) + rng.normal())
        rows.append(r)
    return rows


def claim(rows):
    se_b, se_c, _ = S.walkforward(rows, "erp_level", "dd", S.H3)
    d = se_b - se_c
    return S.block_boot(d)[1][0] > 0


if __name__ == "__main__":
    found = sum(claim(synth(effect=1.5, seed=s)) for s in range(8))
    false = sum(claim(synth(effect=0.0, seed=100 + s)) for s in range(20))
    weak = sum(claim(synth(effect=0.6, seed=300 + s)) for s in range(8))
    print(f"(power note: a MODERATE planted effect, 0.6 of the noise sd, is found {weak}/8 at this sample size)")
    print(f"strong planted ERP effect found: {found}/8")
    print(f"noise: ERP falsely claimed to help {false}/20")
    ok = found >= 6 and false <= 2
    print("SELFTEST", "OK" if ok else "FAILED")
    raise SystemExit(0 if ok else 1)
