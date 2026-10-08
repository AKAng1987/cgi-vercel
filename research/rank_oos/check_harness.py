"""check_harness.py -- must find a planted persistent per-instrument edge, and must not find one in noise."""
import numpy as np
import study


def synth(tau, seed, n_t=120, combos=8, eps=30, sigma=6.0):
    rng = np.random.default_rng(seed)
    true = {(t, c): rng.normal(0, tau) for t in range(n_t) for c in range(combos)}
    tickers = {}
    for c in range(combos):
        for e in range(eps):
            start = f"2000-{c+1:02d}-{e+1:02d}"
            for t in range(n_t):
                if rng.random() < 0.8:
                    r = true[(t, c)] + rng.normal(0, sigma)
                    occ = {"start_date": start, "return_pct": r, "high_pct": max(r, 0) + abs(rng.normal(2, 1)),
                           "low_pct": min(r, 0) - abs(rng.normal(2, 1))}
                    tickers.setdefault(f"T{t}", {"combos": {}})["combos"].setdefault(str(c), []).append(occ)
    return tickers


def claims(res, m="RAW"):
    return res["summary"][m]["spread_pct"]["ci95"][0] > 0


found = sum(claims(study.run(synth(tau=1.5, seed=s))) for s in range(8))
false = sum(claims(study.run(synth(tau=0.0, seed=100 + s))) for s in range(20))
print(f"planted persistent edge found: {found}/8")
print(f"noise: an edge falsely claimed {false}/20")
ok = found >= 6 and false <= 2
print("SELFTEST", "OK" if ok else "FAILED"); raise SystemExit(0 if ok else 1)
