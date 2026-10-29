"""fetch_data.py -- SPX daily closes and the compass / grid quadrant history for the capex_state study (AWS CLI, read-only).
The capex snapshot itself (data/snapshot.json) is built by ~/market-dashboard/scripts/capex_build.py --out data/snapshot.json
(SEC filings; about 8 minutes). Offline afterwards."""
import json, pathlib, subprocess, sys
REGION = "ap-southeast-1"
HERE = pathlib.Path(__file__).resolve().parent / "data"
HERE.mkdir(exist_ok=True)


def aws(*a):
    p = subprocess.run(["aws", *a, "--region", REGION, "--output", "json"], capture_output=True, text=True)
    if p.returncode:
        sys.exit(f"aws failed: {p.stderr[:300]}")
    return json.loads(p.stdout or "{}")


def query(table, cond, vals, proj, names=None):
    out, key = [], None
    while True:
        a = ["dynamodb", "query", "--table-name", table, "--key-condition-expression", cond,
             "--expression-attribute-values", json.dumps(vals), "--projection-expression", proj]
        if names:
            a += ["--expression-attribute-names", json.dumps(names)]
        if key:
            a += ["--exclusive-start-key", json.dumps(key)]
        r = aws(*a)
        out += r.get("Items", [])
        key = r.get("LastEvaluatedKey")
        if not key:
            return out


items = query("cmon-stage-backend-price-history", "symbol = :s", {":s": {"S": "SPX"}}, "#d, #c", {"#d": "date", "#c": "close"})
out = {"SPX": sorted((i["date"]["S"], float(i["close"]["N"])) for i in items)}
for m in ("compass_US", "grid_US"):
    items = query("cmon-stage-backend-model-history", "model_name = :m", {":m": {"S": m}}, "metrics_date, quadrant")
    out[m] = sorted((i["metrics_date"]["S"], int(i["quadrant"]["N"])) for i in items)
for k, v in out.items():
    print(f"{k:12} {len(v):6} rows  {v[0][0]} -> {v[-1][0]}")
(HERE / "inputs.json").write_text(json.dumps(out))
