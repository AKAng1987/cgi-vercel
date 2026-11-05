"""check_harness.py -- each of the three arms must FIND a planted effect (>= 6/8) and not invent one from no-effect data (<= 2/20).
Synthetic 10-asset returns (7 'equity', 3 'commodity') on the real trading calendar with the real Compass labels; every run goes through the same
S.schedule / S.simulate / S.primary code as run.py. Plant 1: group drift flips with the regime. Plant 2: persistent 2-state volatility, constant expected return.
Plant 3 (judged on volatility, Amendment 1): a regime-dependent hedge group (the one a regime-aware min-variance can use)."""
import numpy as np
import study as S

D = S.D
DATES, REAL = S.load()
BUCKET, QUAD = S.labels(DATES, 1)
N, T = 10, len(DATES)
RF = np.zeros(T)


def _corr(base=0.5):
    R = np.full((N, N), base); np.fill_diagonal(R, 1.0); return R


def corr3(g, state):
    """risk group (0-5), hedge group H1 (6-7... here 4 of the remaining), H2: state 1 H1 hedges (-g), H2 adds (+g); state 2 reverses."""
    R = np.zeros((N, N)); R[:5, :5] = 0.5; R[5:8, 5:8] = 0.4; R[8:, 8:] = 0.4; R[5:8, 8:] = 0.1; R[8:, 5:8] = 0.1
    a, b = (-g, g) if state == 1 else (g, -g)
    R[:5, 5:8] = a; R[:5, 8:] = b; R[5:8, :5] = a; R[8:, :5] = b
    np.fill_diagonal(R, 1.0); return R


def synth(arm, eff, seed):
    rng = np.random.default_rng(seed)
    vols = rng.uniform(0.009, 0.011, N)
    mu = np.full(N, 0.0003)
    out = np.zeros((T, N))
    if arm == 1:                                    # group drift depends on the regime: eq - cm = +/- eff per day
        for k, sgn in ((1, 1), (2, -1), (3, -1), (-1, 0)):
            m = np.where(BUCKET == k)[0]
            mu_k = mu.copy(); mu_k[S.EQ] += sgn * eff / 2; mu_k[S.CM] -= sgn * eff / 2
            out[m] = rng.multivariate_normal(mu_k, np.outer(vols, vols) * _corr(), size=len(m))
    elif arm == 2:                                  # persistent volatility states, constant expected return; eff = vol ratio - 1
        st = np.zeros(T, int); p = 0.98
        for t in range(1, T):
            st[t] = st[t - 1] if rng.random() < p else 1 - st[t - 1]
        scale = np.where(st == 1, 1 + eff, 1.0)
        out = rng.multivariate_normal(np.zeros(N), np.outer(vols, vols) * _corr(), size=T) * scale[:, None] + mu
    else:                                           # regime-dependent hedge group, eff = gap
        for k, stt in ((1, 1), (2, 2), (3, 2), (-1, 2)):
            m = np.where(BUCKET == k)[0]
            out[m] = rng.multivariate_normal(mu, np.outer(vols, vols) * corr3(eff, stt), size=len(m))
    return np.hstack([out, np.zeros((T, 1))])


def claim(arm, eff, seed, n_boot=500):
    rets = synth(arm, eff, seed)
    days, W = S.schedule(rets, DATES, BUCKET, QUAD)
    R = {k: S.simulate(rets, days, W[k])[0] for k in ("EW", "V", "G0", "T1", "B4e", "C")}
    rf = rets[days[0]:, S.CASH]
    idx = D.block_idx(len(R["C"]), n_boot, np.random.default_rng(seed + 7))
    out = S.primary(R, rf, idx)[f"P{arm}"]
    return out[1][1] > 0 if arm == 2 else out[0]          # arm 2: would-be claim (P2 is descriptive in the study)


PLANT = {1: 0.0006, 2: 4.0, 3: 0.35}
SWEEP = {1: (0.0001, 0.0002, 0.0004), 2: (1.0, 2.0), 3: (0.05, 0.1, 0.2)}
NOISE = {1: 0.0, 2: 0.0, 3: 0.0}
LABEL = {1: "regime tilt (group drift gap per day)", 2: "volatility sizing (vol ratio - 1)", 3: "regime correlations (hedge gap)"}

if __name__ == "__main__":
    ok = True
    for arm in (1, 3, 2):
        found = sum(claim(arm, PLANT[arm], s) for s in range(8))
        false = sum(claim(arm, NOISE[arm], 100 + s) for s in range(20))
        print(f"arm {arm} {LABEL[arm]}: plant {PLANT[arm]} found {found}/8; no effect: false claim {false}/20")
        sw = {e: sum(claim(arm, e, 1000 + s) for s in range(8)) for e in SWEEP[arm]}
        for e, v in sw.items():
            print(f"    effect {e}: found {v}/8")
        sm = next((e for e in sorted(sw) if sw[e] >= 6), None)
        print(f"    smallest effect found in 6/8 of those tried: {sm if sm is not None else 'above ' + str(max(SWEEP[arm]))}")
        if arm != 2:
            ok = ok and found >= 6 and false <= 2
        else:
            print('    (information only: P2 is descriptive after PREREG Amendment 1; a Sharpe test cannot see vol timing of this size in 17 years)')
    print("SELFTEST", "OK" if ok else "FAILED")
    raise SystemExit(0 if ok else 1)
