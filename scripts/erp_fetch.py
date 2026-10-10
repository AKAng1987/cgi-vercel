"""
erp_fetch.py -- manual loader for Aswath Damodaran's implied equity risk premium (monthly + annual). Zero tokens.

Day to day the API keeps itself current: api/erp_data.sync_if_due() runs from /api/freshness, which the 08:15 refresh
routine reads every morning. This script is for the one-time history load and for checking by hand.

  python3 scripts/erp_fetch.py --check      # did either workbook change since we last stored it? (HEAD only)
  python3 scripts/erp_fetch.py --dry-run    # parse both workbooks and print what would be stored; writes nothing
  python3 scripts/erp_fetch.py --history    # write every missing row straight to DynamoDB (AWS CLI); idempotent

Source: Damodaran, NYU Stern, https://pages.stern.nyu.edu/~adamodar/  -- credit him wherever a figure is shown.
Stored as ERP_* symbols in the price-history table (api/series_write.ALLOWED_EXTERNAL); values in percent.
"""
from __future__ import annotations

import argparse, datetime as dt, json, os, pathlib, subprocess, sys, time, urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "api"))
import erp_parse  # noqa: E402  (stdlib only)

TABLE, REGION = "cmon-stage-backend-price-history", "ap-southeast-1"
STATE = pathlib.Path(os.environ.get("ERP_STATE", "~/.cgi/erp_state.json")).expanduser()


def fetch(url: str, method: str = "GET") -> urllib.request.addinfourl:
    return urllib.request.urlopen(urllib.request.Request(url, method=method, headers={"User-Agent": "Mozilla/5.0 (cgi erp_fetch)"}), timeout=60)


def aws(*args: str) -> dict:
    p = subprocess.run(["aws", *args, "--region", REGION, "--output", "json"], capture_output=True, text=True)
    if p.returncode:
        raise SystemExit(f"aws {' '.join(args[:2])} failed: {p.stderr.strip()[:300]}")
    return json.loads(p.stdout or "{}")


def held_dates(sym: str) -> set[str]:
    out, key = set(), None
    while True:
        a = ["dynamodb", "query", "--table-name", TABLE, "--key-condition-expression", "symbol = :s",
             "--expression-attribute-values", json.dumps({":s": {"S": sym}}),
             "--projection-expression", "#d", "--expression-attribute-names", '{"#d":"date"}']
        if key:
            a += ["--exclusive-start-key", json.dumps(key)]
        r = aws(*a)
        out |= {i["date"]["S"] for i in r.get("Items", [])}
        key = r.get("LastEvaluatedKey")
        if not key:
            return out


def write_rows(series: dict[str, list[tuple[str, float]]]) -> int:
    n = 0
    for sym, rows in series.items():
        have = held_dates(sym)
        todo = [(d, v) for d, v in rows if d not in have]
        for i in range(0, len(todo), 25):
            req = {TABLE: [{"PutRequest": {"Item": {
                "symbol": {"S": sym}, "date": {"S": d}, "source": {"S": "damodaran"}, "source_symbol": {"S": sym},
                "close": {"N": repr(v)}}}} for d, v in todo[i:i + 25]]}
            for attempt in range(5):
                req = (aws("dynamodb", "batch-write-item", "--request-items", json.dumps(req)).get("UnprocessedItems") or {})
                if not req:
                    break
                time.sleep(1 + attempt)
            else:
                raise SystemExit(f"{sym}: batch still unprocessed after retries")
        print(f"  {sym:18} wrote {len(todo):4} ({len(have)} already held)")
        n += len(todo)
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    for f in ("check", "dry-run", "history"):
        g.add_argument("--" + f, action="store_true")
    a = ap.parse_args()
    urls = {"monthly": erp_parse.MONTHLY_URL, "annual": erp_parse.ANNUAL_URL}
    if a.check:
        seen = json.loads(STATE.read_text()) if STATE.exists() else {}
        for k, u in urls.items():
            lm = fetch(u, "HEAD").headers.get("Last-Modified", "")
            print(f"{k}: file last-modified {lm}; stored {seen.get(k)} -> {'CHANGED' if lm != seen.get(k) else 'unchanged'}")
        return 0
    mod = {k: fetch(u, "HEAD").headers.get("Last-Modified", "") for k, u in urls.items()}
    series = {**erp_parse.parse_monthly(fetch(urls["monthly"]).read(erp_parse.MAX_BYTES + 1)),
              **erp_parse.parse_annual(fetch(urls["annual"]).read(erp_parse.MAX_BYTES + 1))}
    for sym, rows in series.items():
        print(f"  {sym:18} {len(rows):4} rows  {rows[0][0]} -> {rows[-1][0]}  latest {rows[-1][1]}")
    if a.dry_run:
        return 0
    n = write_rows(series)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({**mod, "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}, indent=1))
    print(f"done: {n} rows stored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
