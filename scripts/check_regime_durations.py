"""check_regime_durations.py -- arithmetic check for api/regime_durations.py on synthetic rows.

    python3 scripts/check_regime_durations.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
import regime_durations as rd  # noqa: E402

# compass: 1 for 10d, 2 for 20d (repeat event inside a run must not split it), then 1 open
compass = [("2026-01-01", 1), ("2026-01-11", 2), ("2026-01-21", 2), ("2026-01-31", 1)]
grid = [("2026-01-01", 3), ("2026-01-16", 4)]
out = rd.compute(compass, grid, "2026-02-10")

c = out["compass"]
assert c["overall"]["n"] == 2 and c["overall"]["mean_days"] == 15, c["overall"]   # 10 and 20 completed
assert c["by_regime"]["2"]["median_days"] == 20, "same-quadrant repeat split a run"
assert c["current"]["regime"] == "1" and c["current"]["age_days"] == 10, c["current"]

m = out["combined"]
# C1G3 Jan1-11 (10d), C2G3 Jan11-16 (5d), C2G4 Jan16-31 (15d), C1G4 open since Jan31
assert [m["by_regime"][k]["median_days"] for k in ("C1G3", "C2G3", "C2G4")] == [10, 5, 15], m["by_regime"]
assert "C1G4" not in m["by_regime"], "open run leaked into completed stats"
assert m["current"]["regime"] == "C1G4" and m["current"]["age_days"] == 10, m["current"]
assert m["overall"]["thin"] and m["overall"]["anecdotal"], "n=3 must flag thin and anecdotal"
print("OK: regime_durations arithmetic, open-run exclusion and thin/anecdotal flags")
