"""sensitivity.py -- how fragile is the PRIMARY result to the choices made in run.py? Descriptive; claims nothing new.
Varies: minimum training releases, settle window, the excluded GDP rows, and checks the release->flip date offsets."""
import json, pathlib, datetime as dt
import consensus_study as C

HERE = pathlib.Path(__file__).resolve().parent
rel = json.loads((HERE / "data" / "releases.json").read_text())
grid = json.loads((HERE / "data" / "inputs.json").read_text())["grid_US"]
growth = C.axis_series(grid, "growth")
EXC = {"2013-03-28", "2013-06-26", "2013-09-26", "2025-10-30"}
base = [r for r in rel["gdp"] if r.get("indicator") == "GDP Growth Rate" and r.get("est") == "adv"
        and r["forecast"] is not None and r["previous"] is not None and r["date"][:10] <= "2026-10-01"]
out = {}
print("min_train  settle  excl-rule  n_scored  diff      95% CI              verdict")
for mt in (10, 15, 20, 25, 30):
    for settle in (1, 3, 5):
        for label, rows in (("as run", [r for r in base if r["date"][:10] not in EXC]), ("keep all adv", base)):
            C.SETTLE_DAYS = settle
            built = []
            for r in rows:
                st, fl = C.flip_after(growth, r["date"][:10], settle)
                if st is None:
                    continue
                built.append({"date": r["date"][:10], "state": st, "flip": fl, "g": C.oriented_gap(r["forecast"], r["previous"], st),
                              "forecast": r["forecast"], "previous": r["previous"], "actual": r["actual"]})
            c = C.compare(built, mt)
            if "diff" in c:
                out[f"{mt}/{settle}/{label}"] = c
                print(f"{mt:9d}  {settle:6d}  {label:12s}  {c['n_scored']:8d}  {c['diff']:+.4f}  [{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}]  {c['verdict']}")

# release -> flip date offsets (where a flip is matched), and growth flips not tied to an advance release
offs, matched = [], set()
for r in base:
    d0 = dt.date.fromisoformat(r["date"][:10])
    for k in range(0, 6):
        d = (d0 + dt.timedelta(days=k)).isoformat()
        prev = [s for dd, s in growth if dd < d]
        cur = [s for dd, s in growth if dd == d]
        if cur and prev and cur[0] != prev[-1]:
            offs.append(k); matched.add(d); break
flips = [d for (d, s), (d0, s0) in zip(growth[1:], growth[:-1]) if s != s0]
print("\noffset (days) from advance release to flip stamp:", {k: offs.count(k) for k in sorted(set(offs))})
print(f"growth flips in model history: {len(flips)}; matched to an advance release within 5 days: {len(matched)}")
print("unmatched flip dates (2nd/final estimates or off-calendar):", [d for d in flips if d not in matched][:30])
(HERE / "sensitivity.json").write_text(json.dumps(out, indent=1, default=float))
