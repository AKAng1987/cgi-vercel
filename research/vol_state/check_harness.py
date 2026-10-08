"""check_harness.py -- the HMM must recover a known hidden state, and the comparison must not invent a winner."""
import numpy as np
import hmm, study


def synth(n=4000, seed=0, sd=(0.006, 0.02), stay=(0.99, 0.96), mu=(0.0003, 0.0003)):
    rng = np.random.default_rng(seed)
    s = np.zeros(n, int)
    for t in range(1, n):
        s[t] = s[t - 1] if rng.random() < stay[s[t - 1]] else 1 - s[t - 1]
    return rng.normal(np.array(mu)[s], np.array(sd)[s]), s


ok_fit = 0
for seed in range(8):
    x, s = synth(seed=seed)
    p = hmm.fit(x)
    probs = hmm.filter_next(x, p)
    hit = ((probs[:-1] > 0.5) == (s[1:] == 1)).mean()
    ok_fit += abs(p["sd"][0] / 0.006 - 1) < 0.15 and abs(p["sd"][1] / 0.02 - 1) < 0.15 and hit > 0.85
print(f"recovers the hidden calm/stormy states (sd within 15%, state hit-rate > 85%): {ok_fit}/8")

# Noise: two random sizing rules of identical skill must not be called different.
false = 0
for seed in range(20):
    rng = np.random.default_rng(100 + seed)
    r = rng.normal(0.0003, 0.01, 3000)
    a = r * rng.uniform(0.5, 1.5, 3000); b = r * rng.uniform(0.5, 1.5, 3000)
    lo, hi = study.sharpe_diff_boot(a, b, reps=400)["ci95"]
    false += lo > 0 or hi < 0
print(f"noise: a winner was falsely claimed {false}/20")

# Power note: with the SAME mean return in both states, even perfect knowledge of the state adds only ~0.1 Sharpe,
# which 40 years of daily data cannot separate from luck. Reported, not gated on.
weak = 0
for seed in range(8):
    x, s = synth(n=10000, seed=300 + seed)
    w = np.where(s == 1, 0.3, 1.0)
    weak += study.sharpe_diff_boot(w * x, x, reps=400)["ci95"][0] > 0
print(f"(power note: equal-mean states, perfect-knowledge sizing detected only {weak}/8)")

# Planted: stormy state loses money on average (as real markets tend to); true-state sizing must be detected.
found = 0
for seed in range(8):
    x, s = synth(n=10000, seed=200 + seed, mu=(0.0005, -0.0006))
    w = np.where(s == 1, 0.3, 1.0)
    lo, hi = study.sharpe_diff_boot(w * x, x, reps=400)["ci95"]
    found += lo > 0
print(f"planted: true-state sizing detected as better: {found}/8")
ok = ok_fit >= 6 and false <= 2 and found >= 6
print("SELFTEST", "OK" if ok else "FAILED"); raise SystemExit(0 if ok else 1)
