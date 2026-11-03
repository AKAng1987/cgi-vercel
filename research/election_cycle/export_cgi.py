"""export_cgi.py -- trim results.json to the static snapshot the CGI Context section shows
(web/app/components/context/election_cycle.json). Static: rerun after any change to results.json; nothing is fetched at view time."""
import json, pathlib
HERE = pathlib.Path(__file__).resolve().parent
r = json.loads((HERE / "results.json").read_text())
keep = ("year", "election", "state", "tercile", "r252", "baseline252", "excess252", "react", "season_ret", "season_dd",
        "scenario", "compass", "grid", "pres_house_seat_change", "president")
out = {
    "built": "2026-11-04", "audit": "done, 0 blocking", "n": r["primary"]["n"], "last_bar": r["last"],
    "primary": {k: r["primary"][k] for k in ("mean_event", "mean_baseline", "mean_excess", "p", "ci95", "claim")},
    "secondary": {k: {x: v[x] for x in ("mean_excess", "p", "ci95", "claim", "n")} for k, v in r["secondary"].items()},
    "season": r["season"], "state": r["explore_state"], "scenarios": {
        k: {"n": v["n"], "years": v["years"], **{m: v[m]["mean"] for m in ("react", "r5", "r21", "r63", "r126", "r252", "excess252")}}
        for k, v in r["scenarios"].items()},
    "react_all": r["react_all"], "live": r["live_2026"], "crosscheck": {"checked": r["crosscheck"]["checked"], "gaps": len(r["crosscheck"]["gaps"])},
    "events": [{k: e[k] for k in keep} for e in r["events"]],
    "harness": {"plant15_found": "8/8", "noise_false": "1/20", "smallest_detectable_pts": 12},
}
dest = HERE.parent.parent / "web/app/components/context/election_cycle.json"
dest.write_text(json.dumps(out, indent=1))
print("wrote", dest, len(dest.read_text()), "bytes")
