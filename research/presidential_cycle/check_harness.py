"""check_harness.py -- self-test for both parts (repo standard: find a planted effect in >= 6/8, invent none from noise in > 2/20).
A: the real 19 presidential Election Days moved by a random circular offset inside 1950-2025; +15 points planted on their 252-day return.
B: 19 random years from 1950-2024; +10 points planted on their Jan-Jun return; label-permutation test (two-sided, p < 0.05)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "election_cycle"))
import numpy as np
import election_study as S
import elections_pres as P

dates, c = S.load_spx()
V = S.vol20(c)
T = S.expanding_terciles(V)
F = S.forward(c, 252)
N = len(c)
FIRST = int(np.searchsorted(np.array(dates), "1950-01-01"))
REAL_IDX = np.array([S.bar_before(dates, str(d)) for d in P.DATES.values()])


def draw(rng):
    L = N - 253 - FIRST
    return FIRST + (REAL_IDX - FIRST + int(rng.integers(0, L))) % L


def claim_a(effect, seed, n_boot=600):
    rng = np.random.default_rng(seed)
    idx = draw(rng)
    return S.excess_test(F[idx] + effect, T[idx], idx, T, F, rng, first=FIRST, n_boot=n_boot)["claim"]


JJ = np.array([c[S.bar_before(dates, f"{y}-07-01")] / c[S.bar_before(dates, f"{y}-02-01")] - 1 for y in range(1950, 2025)])


def claim_b(effect, seed, n_perm=2000):
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(JJ), 19, replace=False)
    rest = np.setdiff1d(np.arange(len(JJ)), pick)
    _, p = S.diff_perm(JJ[pick] + effect, JJ[rest], rng, n=n_perm)
    return p < 0.05


def curve(fn, effects, runs=40):
    return {e: sum(fn(e, 1000 + s) for s in range(runs)) / runs for e in effects}


if __name__ == "__main__":
    okall = True
    for name, fn, plant, effects in (("A (12-month excess after the vote)", claim_a, 0.15, (0.05, 0.08, 0.10, 0.12, 0.15)),
                                     ("B (Jan-Jun return, presidential vs other years)", claim_b, 0.10, (0.03, 0.05, 0.07, 0.10))):
        found = sum(fn(plant, s) for s in range(8))
        false = sum(fn(0.0, 100 + s) for s in range(20))
        print(f"{name}: planted +{plant*100:.0f} points found {found}/8; noise falsely claimed {false}/20")
        pw = curve(fn, effects)
        for e, v in pw.items():
            print(f"   power at +{e*100:.0f} points: {v*100:.0f}% (40 runs)")
        sde = next((e for e in sorted(pw) if pw[e] >= 0.8), None)
        print("   smallest effect detectable at 80% power:", f"+{sde*100:.0f} points" if sde else f"above +{max(effects)*100:.0f} points")
        okall &= found >= 6 and false <= 2
    print("SELFTEST", "OK" if okall else "FAILED")
    raise SystemExit(0 if okall else 1)
