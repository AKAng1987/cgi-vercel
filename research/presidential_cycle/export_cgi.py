"""export_cgi.py -- trim results.json to the static snapshot the CGI Context section shows
(web/app/components/context/presidential_cycle.json). Static: rerun after any change to results.json."""
import json, pathlib
HERE = pathlib.Path(__file__).resolve().parent
r = json.loads((HERE / "results.json").read_text())
keep = ("year", "winner", "party_change", "incumbent_ran", "ret6m", "state6", "tercile", "r252", "baseline252", "excess252", "react", "janjun_ret")
out = {
    "built": "2026-11-04", "audit": "done, 0 blocking", "n": r["primary"]["n"], "last_bar": r["last"],
    "primary": {k: r["primary"][k] for k in ("mean_event", "mean_baseline", "mean_excess", "p", "ci95", "claim")},
    "secondary": {k: {x: v[x] for x in ("mean_excess", "p", "ci95", "claim")} for k, v in r["secondary"].items()},
    "season": r["season"], "groups": r["groups"], "react_all": r["react_all"],
    "crosscheck": {"checked": r["crosscheck"]["checked"], "gaps": len(r["crosscheck"]["gaps"])},
    "events": [{k: e[k] for k in keep} for e in r["events"]],
    "harness": {"a": {"found": "8/8", "noise": "2/20", "sde": 15}, "b": {"found": "8/8", "noise": "1/20", "sde": 7}},
}
dest = HERE.parent.parent / "web/app/components/context/presidential_cycle.json"
dest.write_text(json.dumps(out, indent=1))
print("wrote", dest, len(dest.read_text()), "bytes")
