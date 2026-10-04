"""
selftest.py -- the harness must find a planted signal AND must not invent one.
Run this before believing any number score.py produces.
"""
import numpy as np
import latent, score

def synth(n=240, K=10, signal=0.0, seed=1, miss=0.25):
    rng = np.random.default_rng(seed)
    f = np.zeros(n)
    for t in range(1, n):
        f[t] = 0.6 * f[t - 1] + rng.normal() * 0.8
    lam = rng.uniform(0.5, 0.9, K)
    Y = f[:, None] * lam + rng.normal(size=(n, K)) * 0.6
    Y[rng.random(Y.shape) < miss] = np.nan            # ragged edge
    state = (rng.random(n) < 0.5).astype(int)
    p = 1 / (1 + np.exp(-(-1.0 + signal * f)))
    y = (rng.random(n) < p).astype(int)
    wins = [{"state": int(state[t]), "flip": int(y[t]),
             "r_pub": {f"d{k}": (None if np.isnan(Y[t, k]) else float(Y[t, k])) for k in range(K)}} for t in range(n)]
    return {"windows": wins, "drivers": [f"d{k}" for k in range(K)]}, f

# 1. the filter recovers a latent factor it was never shown
block, f = synth(signal=0.0)
Y = score.matrix(block["windows"], block["drivers"], "r_pub")
fit = latent.fit_factor(Y)
fh, _ = latent.filter_factor(Y, fit)
corr = abs(np.corrcoef(fh, f)[0, 1])
print(f"[1] filtered factor vs true factor |corr| = {corr:.2f}   (need > 0.8, with 25% of readings missing)")
assert corr > 0.8

# 2. planted signal: should beat the base rate
wins_ = []
for seed in range(8):
    blk, _ = synth(signal=1.5, seed=seed)
    r = score.score_axis("synthetic", blk)
    wins_.append(r.brier["M1"] < r.brier["B0"])
print(f"[2] planted signal: M1 beats B0 on Brier in {sum(wins_)}/8 seeds   (need >= 6)")
assert sum(wins_) >= 6

# 3. NO signal: must NOT systematically beat the base rate
fp = 0
for seed in range(20):
    blk, _ = synth(signal=0.0, seed=100 + seed)
    r = score.score_axis("null", blk)
    b = r.boot["M1_vs_B0_brier"]
    fp += int(b["ci95"][1] < 0)                      # CI entirely below zero == a claimed win
print(f"[3] null data: M1 claims a significant win in {fp}/20 seeds   (need <= 2; chance alone ~1)")
assert fp <= 2
print("selftest OK")
