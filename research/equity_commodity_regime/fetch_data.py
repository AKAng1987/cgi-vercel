"""fetch_data.py -- dividend-adjusted daily closes (Yahoo chart API, urllib, no key) for the 10 risk sleeves and SHY, plus the CGI regime history.
Offline afterwards. Writes data/yahoo.json, data/regime_history.json."""
import json, pathlib, shutil, subprocess, sys, urllib.request, datetime as dt
HERE = pathlib.Path(__file__).resolve().parent / "data"
HERE.mkdir(exist_ok=True)
SLEEVES = ["SPY", "QQQ", "IWM", "EWJ", "EWG", "FXI", "EWZ", "DBC", "GLD", "USO", "SHY"]
EXTRA = []
out = {}
for s in SLEEVES + EXTRA:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{s}?period1=1000000000&period2=1800000000&interval=1d&events=history"
    r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read())["chart"]["result"][0]
    ts, q, adj = r["timestamp"], r["indicators"]["quote"][0]["close"], r["indicators"]["adjclose"][0]["adjclose"]
    rows = [(dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"), float(c), float(a)) for t, c, a in zip(ts, q, adj) if c is not None and a is not None]
    out[s] = rows
    print(f"{s:8} {len(rows):6} rows {rows[0][0]} -> {rows[-1][0]}")
(HERE / "yahoo.json").write_text(json.dumps(out))
rh = pathlib.Path.home() / "brain-journal/data/regime_history.json"
shutil.copy(rh if rh.exists() else HERE.parent.parent / "regime_diversification/data/regime_history.json", HERE / "regime_history.json")
