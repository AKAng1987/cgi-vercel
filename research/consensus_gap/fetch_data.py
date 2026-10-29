"""fetch_data.py -- model state history for the consensus-gap study (AWS CLI, read-only; no boto3).

grid_US   : growth (slot 0) and inflation (slot 1) quadrant history, rows (metrics_date, quadrant)
compass_US: liquidity / credit, kept only for the descriptive lag check

The release consensus data (data/releases.json) comes from the TradingView economic calendar, which is only reachable
from inside a Claude session; it was fetched once, a year at a time, and saved. Offline from here on.
"""
import json, pathlib, subprocess, sys
REGION = "ap-southeast-1"
HERE = pathlib.Path(__file__).resolve().parent / "data"
HERE.mkdir(exist_ok=True)


def aws(*a):
    p = subprocess.run(["aws", *a, "--region", REGION, "--output", "json"], capture_output=True, text=True)
    if p.returncode:
        sys.exit(f"aws failed: {p.stderr[:300]}")
    return json.loads(p.stdout or "{}")


def model(name):
    out, key = [], None
    while True:
        a = ["dynamodb", "query", "--table-name", "cmon-stage-backend-model-history",
             "--key-condition-expression", "model_name = :m", "--expression-attribute-values",
             json.dumps({":m": {"S": name}}), "--projection-expression", "metrics_date, quadrant"]
        if key:
            a += ["--exclusive-start-key", json.dumps(key)]
        r = aws(*a)
        out += r.get("Items", [])
        key = r.get("LastEvaluatedKey")
        if not key:
            return sorted((i["metrics_date"]["S"], int(i["quadrant"]["N"])) for i in out)


out = {m: model(m) for m in ("grid_US", "compass_US")}
for k, v in out.items():
    print(f"{k:12} {len(v):5} rows  {v[0][0]} -> {v[-1][0]}")
(HERE / "inputs.json").write_text(json.dumps(out))
