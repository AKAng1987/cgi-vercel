"""check_harness.py -- must find a planted peer reversion and must not find one in noise."""
import numpy as np, pandas as pd
import study


def synth(rev, seed, n=2500, groups=4, per=8):
    rng = np.random.default_rng(seed)
    cols, g = [], {}
    data = {}
    mkt = rng.normal(0, 0.01, n)
    for gi in range(groups):
        gf = rng.normal(0, 0.006, n)
        for j in range(per):
            c = f"G{gi}_{j}"; g[c] = str(gi)
            e = rng.normal(0, 0.01, n)
            idio = e.copy()
            idio[1:] += rev * e[:-1]          # rev < 0: part of yesterday's own move comes back
            data[c] = mkt + gf + idio
    return pd.DataFrame(data), g


def claims(rets, g):
    res = study.residuals(rets, g)
    b = study.block_boot(study.fade_table(res, 1, 1, cost=0.0), reps=400)
    return b["ci95"][0] > 0


found = sum(claims(*synth(-0.3, s)) for s in range(8))
false = sum(claims(*synth(0.0, 100 + s)) for s in range(20))
print(f"planted reversion found: {found}/8")
print(f"noise: reversion falsely claimed {false}/20")
ok = found >= 6 and false <= 2
print("SELFTEST", "OK" if ok else "FAILED"); raise SystemExit(0 if ok else 1)
