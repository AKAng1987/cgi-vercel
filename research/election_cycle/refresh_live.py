"""refresh_live.py -- zero-token refresh of the 2026 live case (not part of the study; nothing here is counted in any test).
Re-fetches the S&P 500 (Yahoo ^GSPC) and writes web/app/components/context/election_live.json: the return since the 2 Nov 2026 close
at the day after and at +21/+63/+126/+252 trading days (as bars exist), next to the average of the 19 historical midterms, plus the
election result from data/live_result.json (hand-entered once the races are called; the scenario is derived from it, never guessed).
Usage: python refresh_live.py [--no-fetch]"""
import datetime as dt, json, pathlib, subprocess, sys
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ELECTION = "2026-11-03"
BASELINE = "2026-11-02"            # close before Election Day, the same anchor as every historical midterm
PRESIDENT = "R"
WINDOWS = [("day after", None, "react"), ("1 month", 21, "r21"), ("3 months", 63, "r63"), ("6 months", 126, "r126"), ("12 months", 252, "r252")]

if "--no-fetch" not in sys.argv:
    subprocess.run([sys.executable, str(HERE / "fetch_data.py")], check=True)
rows = json.loads((HERE / "data/spx_yahoo.json").read_text())
dates = [d for d, _ in rows]
c = np.array([v for _, v in rows])
# Saturday bars before 1952-06-01 do not matter for 2026; today's bar may be intraday, so drop it unless the date is before today (UTC-5 close)
today = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=21)).strftime("%Y-%m-%d")   # a bar is final once it is a day before "today" US time
keep = [k for k, d in enumerate(dates) if d <= today]
dates, c = [dates[k] for k in keep], c[keep]
b = dates.index(BASELINE)
hist = json.loads((HERE / "results.json").read_text())

res = json.loads((HERE / "data/live_result.json").read_text())
scenario = None
if res.get("status") == "called" and res.get("house_after") in "DR" and res.get("senate_after") in "DR":
    lh, ls = res["house_after"] != PRESIDENT, res["senate_after"] != PRESIDENT
    scenario = ("Pres party loses both (blue-wave analog)" if lh and ls else "Loses House only (Dem House / GOP Senate analog)" if lh
                else "Loses Senate only (the other split)" if ls else "Keeps both (red-wave analog)")

def hist_mean(key, scen=None):
    ev = [e for e in hist["events"] if scen is None or e["scenario"] == scen]
    return float(np.mean([e[key] for e in ev])) if ev else None

out_w = []
for label, bars, key in WINDOWS:
    if bars is None:
        j = next((k for k, d in enumerate(dates) if d > ELECTION), None)
        ret, when = (float(c[j] / c[b] - 1), dates[j]) if j is not None else (None, None)
    else:
        j = b + bars
        ret, when = (float(c[j] / c[b] - 1), dates[j]) if j < len(c) else (None, None)
    out_w.append({"label": label, "bars": bars, "ret": ret, "date": when, "hist_mean": hist_mean(key), "hist_scenario_mean": hist_mean(key, scenario) if scenario else None})

out = {"as_of": dates[-1], "baseline_date": BASELINE, "baseline_close": float(c[b]), "last_close": float(c[-1]),
       "since": float(c[-1] / c[b] - 1) if len(c) - 1 > b else None, "bars_since": len(c) - 1 - b,
       "windows": out_w, "result": {k: res[k] for k in ("status", "house_after", "senate_after", "house_seats_d", "house_seats_r", "source", "as_of")},
       "scenario": scenario, "scenario_n": hist["scenarios"][scenario]["n"] if scenario else None}
dest = HERE.parent.parent / "web/app/components/context/election_live.json"
dest.write_text(json.dumps(out, indent=1))
print(f"live: last bar {out['as_of']}  since baseline {out['since']}  windows filled {sum(w['ret'] is not None for w in out_w)}/{len(out_w)}  result {res['status']}")
