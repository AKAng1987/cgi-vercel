"""fetch_data.py -- bulk SPX daily closes from Yahoo ^GSPC (urllib, no key) into data/spx_yahoo.json, plus the CGI regime history
(compass_US / grid_US) from ~/brain-journal/data/regime_history.json if present. Offline afterwards."""
import json, pathlib, urllib.request, datetime as dt
HERE = pathlib.Path(__file__).resolve().parent / "data"
HERE.mkdir(exist_ok=True)
url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?period1=-1325635200&period2=1800000000&interval=1d&events=history"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
r = json.loads(urllib.request.urlopen(req, timeout=60).read())["chart"]["result"][0]
ts, cl = r["timestamp"], r["indicators"]["quote"][0]["close"]
rows = []
for t, c in zip(ts, cl):
    if c is None:
        continue
    rows.append((dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"), float(c)))
(HERE / "spx_yahoo.json").write_text(json.dumps(rows))
print(f"SPX Yahoo {len(rows)} rows {rows[0][0]} -> {rows[-1][0]}  last close {rows[-1]}")
rh = pathlib.Path.home() / "brain-journal/data/regime_history.json"
if rh.exists():
    (HERE / "regime_history.json").write_text(rh.read_text())
    print("regime history copied")
