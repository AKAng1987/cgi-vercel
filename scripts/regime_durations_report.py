"""regime_durations_report.py -- local, read-only regime duration report.

Reads the live model-history table (the source the Markov layer uses), computes
run lengths with api/regime_durations.py, and writes docs/REGIME_DURATIONS.md
plus docs/regime_durations.json. Nothing is deployed and nothing is written to
AWS. Run it whenever you want fresh numbers (zero tokens):

    python3 scripts/regime_durations_report.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
import regime_durations as rd  # noqa: E402

TABLE = "cmon-stage-backend-model-history"
REGION = "ap-southeast-1"


def load(model: str) -> list[tuple[str, int]]:
    ddb = boto3.client("dynamodb", region_name=REGION)
    kw = dict(TableName=TABLE, KeyConditionExpression="model_name = :m",
              ExpressionAttributeValues={":m": {"S": model}},
              ProjectionExpression="metrics_date, quadrant")
    rows = []
    while True:
        page = ddb.query(**kw)
        rows += [(i["metrics_date"]["S"], int(i["quadrant"]["N"])) for i in page["Items"]]
        if "LastEvaluatedKey" not in page:
            return sorted(rows)
        kw["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def tbl(by: dict, label: str) -> list[str]:
    out = [f"| {label} | n | mean | median | min | max | flag |", "|---|---|---|---|---|---|---|"]
    for k, s in by.items():
        flag = "anecdotal" if s["anecdotal"] else ("thin" if s["thin"] else "")
        out.append(f"| {k} | {s['n']} | {s['mean_days']} | {s['median_days']} | {s['min_days']} | {s['max_days']} | {flag} |")
    return out


def cur(c: dict | None) -> str:
    if not c:
        return "n/a"
    return (f"{c['regime']} since {c['since']}, age {c['age_days']}d; "
            f"{c['survival_pct_same_regime']}% of {c['completed_runs_of_this_regime']} past runs lasted longer "
            f"(median {c.get('same_regime_median_days', 'n/a')}d)")


def main() -> None:
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    comp, grid = load("compass_US"), load("grid_US")
    d = rd.compute(comp, grid, today)
    L = [f"# Regime durations (days, completed runs)", "",
         f"Generated {today} from live model-history (last compass event {comp[-1][0]}, last grid event {grid[-1][0]}).",
         d["caveat"], "", "## In force now"]
    for k in ("combined", "compass", "grid"):
        L.append(f"- **{k}**: {cur(d[k]['current'])}")
    for k, lab in (("combined", "regime"), ("compass", "quadrant"), ("grid", "quadrant")):
        o = d[k]["overall"]
        L += ["", f"## {k.capitalize()} (overall n={o['n']}, mean {o['mean_days']}, median {o['median_days']})"]
        L += tbl(d[k]["by_regime"], lab)
    (ROOT / "docs" / "REGIME_DURATIONS.md").write_text("\n".join(L) + "\n")
    (ROOT / "docs" / "regime_durations.json").write_text(json.dumps(d, indent=2))
    print("\n".join(L[:9]))


if __name__ == "__main__":
    main()
