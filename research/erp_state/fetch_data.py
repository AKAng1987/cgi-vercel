"""fetch_data.py -- dump the series the study needs from CGI's AWS tables into data/*.json (AWS CLI; no boto3).
SPX daily closes, the stored Damodaran ERP series, and the compass / grid quadrant history. Offline afterwards."""
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


def price(sym):
    items = query("cmon-stage-backend-price-history", "symbol = :s", {":s": {"S": sym}}, "#d, #c",
                  {"#d": "date", "#c": "close"})
    return sorted((i["date"]["S"], float(i["close"]["N"])) for i in items)


out = {"SPX": price("SPX")}
for s in ("ERP_T12M", "ERP_TBOND", "ERP_ANNUAL", "ERP_ANNUAL_TBOND"):
    out[s] = price(s)
for m in ("compass_US", "grid_US"):
    items = query("cmon-stage-backend-model-history", "model_name = :m", {":m": {"S": m}}, "metrics_date, quadrant")
    out[m] = sorted((i["metrics_date"]["S"], int(i["quadrant"]["N"])) for i in items)
for k, v in out.items():
    print(f"{k:18} {len(v):6} rows  {v[0][0]} -> {v[-1][0]}")
(HERE / "inputs.json").write_text(json.dumps(out))
