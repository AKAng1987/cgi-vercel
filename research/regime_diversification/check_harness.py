"""check_harness.py -- the method must FIND a planted regime-correlation benefit (>= 6/8) and must NOT invent one from data where the
regimes carry no information (<= 2/20). Also reports the smallest planted gap found in 6/8.
Synthetic 14-asset returns on the real trading calendar and real Compass labels: 7 'risk' assets and 7 'hedge' assets; the cross-group
correlation is structured so a blind matrix averages the hedge away and a regime-aware one keeps it (see corr_for). Primary rule = volatility (PREREG Amendment 1)."""
import sys
import numpy as np
import study as S

DATES, REAL = S.load()
BUCKET, QUAD = S.labels(DATES, 1)
N = REAL.shape[1]
T = len(DATES)


def corr_for(g, state, wa=0.5, wh=0.4, x=0.1):
    """7 risk assets, hedge group H1 (4 assets) and H2 (3). State 1: H1 hedges risk (-g), H2 adds to it (+g); state 2 is the reverse.
    A blind matrix averages the two away; a regime-aware one keeps the right hedge. g <= 0.35 keeps it positive definite."""
    R = np.zeros((N, N)); R[:7, :7] = wa; R[7:11, 7:11] = wh; R[11:, 11:] = wh; R[7:11, 11:] = x; R[11:, 7:11] = x
    a, b = (-g, g) if state == 1 else (g, -g)
    R[:7, 7:11] = a; R[:7, 11:] = b; R[7:11, :7] = a; R[11:, :7] = b
    np.fill_diagonal(R, 1.0)
    return R


def synth(gap, seed, mu=0.0003):
    rng = np.random.default_rng(seed)
    vols = rng.uniform(0.009, 0.011, N)
    out = np.zeros((T, N))
    for k, st in ((1, 1), (2, 2), (3, 2), (-1, 2)):
        m = np.where(BUCKET == k)[0]
        if len(m):
            out[m] = rng.multivariate_normal(np.full(N, mu), np.outer(vols, vols) * corr_for(gap, st), size=len(m))
    return out


def claim(gap, seed, n_boot=500, metric="vol"):
    rets = synth(gap, seed)
    days, W = S.schedule(rets, DATES, BUCKET, QUAD)
    R = {k: S.simulate(rets, days, W[k])[0] for k in ("B3", "B4", "C1")}
    idx = S.block_idx(len(R["C1"]), n_boot, np.random.default_rng(seed + 7))
    return S.primary_claim(R, idx, metric)[0]


if __name__ == "__main__":
    PLANT = 0.35
    found = sum(claim(PLANT, s) for s in range(8))
    false = sum(claim(0.0, 100 + s) for s in range(20))
    print(f"planted cross-group correlation gap +/-{PLANT}: found {found}/8")
    print(f"no regime information (gap 0): false claim {false}/20")
    sweep = {}
    for g in (0.02, 0.04, 0.06, 0.10, 0.20):
        sweep[g] = sum(claim(g, 1000 + s) for s in range(8)); print(f"  gap +/-{g}: found {sweep[g]}/8")
    dd = {g: sum(claim(g, 2000 + s, metric="dd") for s in range(8)) for g in (0.20, 0.35)}
    print(f"(information) the ORIGINAL drawdown primary on the same plants: gap 0.20 found {dd[0.20]}/8, gap 0.35 found {dd[0.35]}/8 -- why PREREG Amendment 1 moved the primary to volatility")
    sm = next((g for g in sorted(sweep) if sweep[g] >= 6), None)
    print("smallest planted gap found in 6/8:", f"+/-{sm}" if sm else "above +/-0.20")
    ok = found >= 6 and false <= 2
    print("SELFTEST", "OK" if ok else "FAILED")
    raise SystemExit(0 if ok else 1)
