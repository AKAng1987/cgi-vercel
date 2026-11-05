"""fetch_data.py -- daily raw and dividend-adjusted closes (Yahoo chart API, urllib, no key) for the sleeve ETFs, CGI's own closes for the same
tickers (to check whether they are price-only), and the CGI regime history (compass_US / grid_US). Offline afterwards.
Writes data/yahoo.json, data/cgi_close.json, data/regime_history.json."""
import json, pathlib, shutil, subprocess, sys, urllib.request, datetime as dt
HERE = pathlib.Path(__file__).resolve().parent / "data"
HERE.mkdir(exist_ok=True)
SLEEVES = ["SPY", "QQQ", "IWM", "EWJ", "EWG", "FXI", "EWZ", "VNQ", "TLT", "IEF", "SHY", "GLD", "DBC", "UUP"]
EXTRA = ["BTC-USD"]
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
shutil.copy(rh if rh.exists() else HERE.parent.parent / "election_cycle/data/regime_history.json", HERE / "regime_history.json")
API = HERE.parents[2] / "api"
sys.path.insert(0, str(API))
import axis_drivers as ad  # noqa: E402
cgi = {}
for s in SLEEVES:
    d, c = ad._load_close(s)
    cgi[s] = list(zip(d, c))
    print("CGI", s, len(d), d[0], d[-1])
(HERE / "cgi_close.json").write_text(json.dumps(cgi))
