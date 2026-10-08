"""check_harness.py -- must find a planted 'crowd reverses' effect, and must not invent one from noise."""
import numpy as np, pandas as pd
import study


def synth(effect, seed, years=18):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2006-01-02", periods=252 * years)
    weeks = pd.date_range(days[0], days[-1], freq="W-TUE")
    spec = pd.Series(np.cumsum(rng.normal(0, 1, len(weeks))), index=weeks)   # positioning random walk
    idx = study.cot_index(spec)
    ev = study.events(idx)
    drift = np.zeros(len(days))
    for d, e in ev.iterrows():                                               # planted: price moves AGAINST the crowd
        p = days.searchsorted(d)
        drift[p:p + 40] += -e["crowd"] * effect
    ret = rng.normal(0.0002, 0.012, len(days)) + drift
    c = pd.Series(100 * np.exp(np.cumsum(ret)), index=days)
    h = c * (1 + np.abs(rng.normal(0, 0.006, len(days)))); l = c * (1 - np.abs(rng.normal(0, 0.006, len(days))))
    return pd.DataFrame({"close": c, "high": h, "low": l}), ev


def claims(effect, seed):
    rows = []
    for k in range(6):                                                        # six instruments per run
        px, ev = synth(effect, seed * 10 + k)
        rows += study.analyse(px, ev, 1)
    df = pd.DataFrame(rows)
    return study.week_boot(df, "ev_40", reps=400)["ci95"][0] > 0


found = sum(claims(0.0015, s) for s in range(8))
false = sum(claims(0.0, 100 + s) for s in range(20))
print(f"planted 'crowd reverses' found: {found}/8")
print(f"noise: a reversal falsely claimed {false}/20")
ok = found >= 6 and false <= 2
print("SELFTEST", "OK" if ok else "FAILED"); raise SystemExit(0 if ok else 1)
