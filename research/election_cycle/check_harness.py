"""check_harness.py -- the method must FIND a planted election effect and must NOT invent one from noise (repo standard >= 6/8, <= 2/20).
Plant: the real election calendar moved by a random circular offset inside 1950-2025 (same spacing, ordinary dates); the effect is added to their 252-day return.
Noise: the same draw with nothing added.  Also reports the smallest effect detectable at 80% power."""
import numpy as np
import election_study as S
import elections as E

dates, c = S.load_spx()
V = S.vol20(c)
T = S.expanding_terciles(V)
F = S.forward(c, 252)
N = len(c)


FIRST = int(np.searchsorted(np.array(dates), "1950-01-01"))      # 1928-49 bars are volatility warm-up, not sample


REAL_IDX = np.array([S.bar_before(dates, str(d)) for d in E.DATES.values()])


def draw(rng):
    """the real 19-election calendar (same spacing) moved by a random circular offset: ordinary dates, midterm spacing."""
    L = N - 253 - FIRST
    return FIRST + (REAL_IDX - FIRST + int(rng.integers(0, L))) % L


def claim(effect, seed, n_boot=600):
    rng = np.random.default_rng(seed)
    idx = draw(rng)
    vals = F[idx] + effect
    r = S.excess_test(vals, T[idx], idx, T, F, rng, first=FIRST, n_boot=n_boot)
    return r["claim"]


if __name__ == "__main__":
    found10 = sum(claim(0.10, s) for s in range(8))
    found = sum(claim(0.15, s) for s in range(8))
    false = sum(claim(0.0, 100 + s) for s in range(20))
    print(f"(information, the original PREREG plant) +10 points found: {found10}/8 -- below 6/8 because power at +10 is only ~55-60%")
    print(f"strong planted effect (+15 points of 12-month excess, PREREG amendment 1) found: {found}/8")
    print(f"noise: an effect falsely claimed {false}/20")
    power = {}
    for eff in (0.03, 0.05, 0.07, 0.08, 0.10, 0.12, 0.15):
        power[eff] = sum(claim(eff, 1000 + s) for s in range(40)) / 40
        print(f"  power at +{eff*100:.0f} points: {power[eff]*100:.0f}% (40 runs)")
    sde = next((e for e in sorted(power) if power[e] >= 0.8), None)
    print("smallest effect detectable at 80% power:", f"+{sde*100:.0f} points (12-month excess)" if sde else "above +15 points")
    ok = found >= 6 and false <= 2
    print("SELFTEST", "OK" if ok else "FAILED")
    raise SystemExit(0 if ok else 1)
