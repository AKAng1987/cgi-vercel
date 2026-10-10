"""
erp_fetch.py -- load Aswath Damodaran's monthly implied equity risk premium into CGI. Zero tokens, standard library only.

Source: https://pages.stern.nyu.edu/~adamodar/pc/implprem/ERPbymonth.xlsx  (start-of-month rows since 2008-09;
Damodaran, NYU Stern. Credit him wherever a figure is shown.) The file is updated around the start of each month.

  python3 scripts/erp_fetch.py --check              # has the file changed since we last stored it? (HEAD only)
  python3 scripts/erp_fetch.py --dry-run            # parse and print what would be stored; writes nothing
  python3 scripts/erp_fetch.py --history            # one-time: write every month straight to DynamoDB (AWS CLI)
  python3 scripts/erp_fetch.py --post               # routine: POST only months newer than the API holds, via the
                                                    # append-only /api/series loader (24 rows per call)

Stored as symbols ERP_* in the price-history table (series_write.ALLOWED_EXTERNAL), value in PERCENT, date = the row's
start-of-month date. The downloaded workbook is treated as untrusted data: parsed with zipfile + ElementTree only,
size-limited, never executed.
"""
from __future__ import annotations

import argparse, datetime as dt, json, os, pathlib, re, subprocess, sys, tempfile, time, urllib.request, zipfile
import xml.etree.ElementTree as ET

URL = "https://pages.stern.nyu.edu/~adamodar/pc/implprem/ERPbymonth.xlsx"
API = os.environ.get("CGI_API_URL", "https://cgi-vercel.vercel.app")
TABLE, REGION = "cmon-stage-backend-price-history", "ap-southeast-1"
STATE = pathlib.Path(os.environ.get("ERP_STATE", "~/.cgi/erp_state.json")).expanduser()
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MAX_BYTES, MAX_UNZIPPED = 5_000_000, 30_000_000

# symbol -> (column in the workbook, min, max); values converted fraction -> percent
COLS = {
    "ERP_T12M": ("J", 0.0, 25.0), "ERP_SUSTAINABLE": ("I", 0.0, 25.0), "ERP_ADJ_RF": ("K", 0.0, 25.0),
    "ERP_NORMALIZED": ("M", 0.0, 25.0), "ERP_NET_CASH": ("N", 0.0, 25.0), "ERP_EXPECTED_RET": ("P", 0.0, 30.0),
    "ERP_TBOND": ("C", 0.0, 20.0), "ERP_GROWTH": ("H", -10.0, 40.0),
}


def http(url: str, method: str = "GET", body: bytes | None = None, timeout: int = 60):
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"User-Agent": "Mozilla/5.0 (cgi erp_fetch)", "Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


def download() -> bytes:
    with http(URL) as r:
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise SystemExit("workbook larger than expected; refusing to parse it")
    return data


def parse(data: bytes) -> dict[str, list[tuple[str, float]]]:
    path = pathlib.Path(tempfile.mkdtemp(prefix="erp_")) / "ERPbymonth.xlsx"
    path.write_bytes(data)
    z = zipfile.ZipFile(path)
    if sum(i.file_size for i in z.infolist()) > MAX_UNZIPPED:
        raise SystemExit("workbook expands too large; refusing to parse it")
    is1904 = bool(re.search(r'date1904="(1|true)"', z.read("xl/workbook.xml").decode("utf-8", "replace")))
    ss = ["".join(t.itertext()) for t in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)]
    base = dt.date(1904, 1, 1) if is1904 else dt.date(1899, 12, 30)
    rows = []
    for r in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter("{%s}row" % NS["m"]):
        cells = {}
        for c in r.findall("m:c", NS):
            v = c.find("m:v", NS)
            if v is not None:
                cells[re.match(r"[A-Z]+", c.get("r")).group(0)] = ss[int(v.text)] if c.get("t") == "s" else v.text
        rows.append(cells)
    if not rows or "Start of month" not in (rows[0].get("A") or ""):
        raise SystemExit("unexpected layout: header row did not start with 'Start of month'")
    out: dict[str, list[tuple[str, float]]] = {k: [] for k in COLS}
    for c in rows[1:]:
        a = (c.get("A") or "").strip()
        try:
            d = base + dt.timedelta(days=int(float(a)))
        except ValueError:
            try:
                d = dt.datetime.strptime(a, "%d-%b-%y").date()
            except ValueError:
                continue
        for sym, (col, lo, hi) in COLS.items():
            try:
                v = float(c[col]) * 100.0
            except (KeyError, ValueError):
                continue          # a month can lack one version (e.g. 2024-09 has no trailing-12-month ERP)
            if lo <= v <= hi:
                out[sym].append((d.isoformat(), round(v, 4)))
    for sym in out:
        out[sym].sort()
    return out


def state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def save_state(**kw) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    s = state(); s.update(kw); STATE.write_text(json.dumps(s, indent=1))


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


def write_history(series: dict[str, list[tuple[str, float]]]) -> int:
    n = 0
    for sym, rows in series.items():
        have = held_dates(sym)
        todo = [(d, v) for d, v in rows if d not in have]
        for i in range(0, len(todo), 25):
            batch = [{"PutRequest": {"Item": {
                "symbol": {"S": sym}, "date": {"S": d}, "source": {"S": "damodaran"}, "source_symbol": {"S": sym},
                "close": {"N": repr(v)}}}} for d, v in todo[i:i + 25]]
            req = {TABLE: batch}
            for attempt in range(5):
                r = aws("dynamodb", "batch-write-item", "--request-items", json.dumps(req))
                req = r.get("UnprocessedItems") or {}
                if not req:
                    break
                time.sleep(1 + attempt)
            else:
                raise SystemExit(f"{sym}: batch still unprocessed after retries")
        print(f"  {sym:18} wrote {len(todo):4} ({len(have)} already held)")
        n += len(todo)
    return n


def post_new(series: dict[str, list[tuple[str, float]]]) -> int:
    with http(f"{API}/api/series", timeout=120) as r:
        held = {s["symbol"]: s["last_date"] for s in json.load(r).get("external", [])}
    if not held:
        raise SystemExit("API does not list external series yet (not deployed?)")
    n = 0
    for sym, rows in series.items():
        last = held.get(sym)
        todo = [(d, v) for d, v in rows if last is None or d > last]
        for i in range(0, len(todo), 24):
            body = json.dumps({"rows": [{"date": d, "value": v} for d, v in todo[i:i + 24]]}).encode()
            with http(f"{API}/api/series/{sym}", "POST", body, timeout=120) as r:
                print("  ", sym, json.load(r))
        n += len(todo)
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    for f in ("check", "dry-run", "history", "post"):
        g.add_argument("--" + f, action="store_true")
    a = ap.parse_args()

    if a.check:
        with http(URL, "HEAD") as r:
            lm = r.headers.get("Last-Modified", "")
        seen = state().get("last_modified")
        print(f"file last-modified: {lm}; we last stored: {seen}")
        print("CHANGED" if lm != seen else "unchanged")
        return 0

    with http(URL, "HEAD") as r:
        lm = r.headers.get("Last-Modified", "")
    series = parse(download())
    head = series["ERP_T12M"]
    print(f"parsed {sum(len(v) for v in series.values())} points over {len(series)} series; "
          f"headline {head[0][0]} -> {head[-1][0]} ({len(head)} months), latest {head[-1][1]}% "
          f"(T-bond {series['ERP_TBOND'][-1][1]}%)")
    if a.dry_run:
        for sym, rows in series.items():
            print(f"  {sym:18} {len(rows):4} rows  {rows[0][0]} -> {rows[-1][0]}  latest {rows[-1][1]}")
        return 0
    n = write_history(series) if a.history else post_new(series)
    save_state(last_modified=lm, stored_through=head[-1][0], at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
    print(f"done: {n} rows stored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
