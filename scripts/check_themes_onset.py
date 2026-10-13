"""check_themes_onset.py -- offline check for the merged-run onset in api/themes_data._run.

    api/.venv/bin/python scripts/check_themes_onset.py

Synthetic series (RS rising, with dips cut in) plus the real EWY case frozen in scripts/fixtures: a mature run
must keep its onset across a one-day dip, a dip of 15+ calendar days must end it, and the age must never snap
back and forth month to month (EWY read 503, 1, 578 under the old 80% rule).
"""
import datetime as dt
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
import themes_data as td  # noqa: E402

START = dt.date(2020, 1, 1)


def series(n, dips=(), floor=None):
    """Daily bars (every calendar day). RS rises 0.2%/day, so it sits above its lagging EMA; each dip (a, b) cuts
    days a..b-1 to 60% of the level, well under trend."""
    d = [(START + dt.timedelta(days=i)).isoformat() for i in range(n)]
    bench = {x: 100.0 for x in d}
    px = {}
    for i, x in enumerate(d):
        v = 100.0 * math.exp(0.002 * i)
        if any(a <= i < b for a, b in dips):
            v *= 0.6
        px[x] = v
    return d, px, bench


def run(n, dips=()):
    d, px, bench = series(n, dips)
    return d, td._run(px, bench)


# 1. no dips: the run starts after the EMA warm-up and never earlier
d, r = run(600)
assert r["status"] == "running" and r["onset"] == d[td.TREND_DAYS], r

# 2. a ONE-day dip two bars before the end keeps the onset (the old rule called this run 1 day old)
d, r = run(600, dips=[(597, 598)])
assert r["status"] == "running" and r["onset"] == d[td.TREND_DAYS], r

# 3. a 10-day dip in the middle is merged
d, r = run(600, dips=[(400, 410)])
assert r["onset"] == d[td.TREND_DAYS], r

# 4. a 16-day dip ends the run: the new run starts after the dip
d, r = run(600, dips=[(400, 416)])
assert r["onset"] == d[416], (r, d[416])

# 5. below trend today -> no active run, with the last day above trend
d, r = run(600, dips=[(595, 600)])
assert r["status"] == "no active run" and r["last_above"] == d[594], r

# 6. a run younger than the warm-up window: onset never reaches into the first 200 bars
d, r = run(450, dips=[(205, 240)])
assert r["onset"] == d[240], r

# 7. too little history
d, r = run(300)
assert r["status"] == "insufficient history", r

# 8. the real EWY case: frozen RS, replayed as of three month ends. The age must grow by about the gap, not snap.
fx = json.loads((ROOT / "scripts" / "fixtures" / "ewy_spy_2016_2026.json").read_text())
dates, px_all, bn_all = fx["dates"], fx["px"], fx["bench_px"]


def as_of(t):
    k = max(i for i, x in enumerate(dates) if x <= t)
    return td._run({dates[i]: px_all[i] for i in range(k + 1)}, {dates[i]: bn_all[i] for i in range(k + 1)})


seen = []
for t in ("2026-06-30", "2026-07-31", "2026-08-31"):
    r = as_of(t)
    assert r["status"] == "running", (t, r)
    seen.append((t, r["onset"], r["age_days"]))
onsets = {o for _t, o, _a in seen}
assert len(onsets) == 1, f"EWY onset moves between month ends: {seen}"
ages = [a for _t, _o, a in seen]
assert ages[0] < ages[1] < ages[2] and ages[2] - ages[0] == 62, seen          # 30 Jun -> 31 Aug = 62 days
print("OK: themes onset -- merged-run rule, EWY stable across", [t for t, _o, _a in seen], "onset", seen[0][1])
