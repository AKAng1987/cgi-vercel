"""measure.py -- re-measure the theme run-length distribution (calibration proof for the merged-run onset rule).

Definition the stage cut-offs (51 / 137 days) and the survival curve were calibrated on (commit 09b52e4, 2026-09-24):
RS = proxy / SPY above its 200-day EMA; dips below trend shorter than 15 days are merged; completed runs shorter than 20
days are discarded; 727 runs, median 82d, mean 138d, p75 182d, p90 328d, over every theme proxy of that date.

    api/.venv/bin/python research/theme_runs/measure.py            # prints the variants and how close each is
Read-only. Prices are cached under research/theme_runs/data/ (git-ignored).
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import json
import statistics as st
import sys
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).resolve().parent / "data"
sys.path.insert(0, str(ROOT / "api"))

# Proxies of the detector on 2026-09-24 (the THEMES dict of commit 09b52e4), plus the standing dollar theme's proxies if any.
PROXIES_0924 = ["AIQ", "ROBO", "BOTZ", "SMH", "SOXX", "WCLD", "SKYY", "FDN", "CIBR", "HACK", "COPX", "CPER", "GDX", "GDXJ",
                "GLD", "SIL", "SLV", "SLX", "XME", "URA", "NLR", "GRID", "XLU", "ITA", "XAR", "XOP", "IEO", "OIH", "CRAK",
                "MLPX", "IBB", "IHI", "XLV", "KBE", "KRE", "XRT", "IBUY", "XLY", "XHB", "VNQ", "XLRE", "SEA", "IYT", "IGF",
                "IDRV", "KARS", "BATT", "TAN", "ICLN", "FAN", "BLOK", "BITO", "KWEB", "FXI", "EWJ", "DBA", "CORN", "WEAT"]
CUTOFF = "2026-09-24"
EMA_N = 200
PUBLISHED = {"n": 727, "median": 82, "mean": 138, "p75": 182, "p90": 328}


def load(sym: str) -> dict[str, float]:
    f = DATA / f"{sym}.json"
    if f.exists():
        return json.loads(f.read_text())
    ddb = boto3.client("dynamodb", region_name="ap-southeast-1")
    kw = dict(TableName="cmon-stage-backend-price-history", KeyConditionExpression="#s = :s",
              ExpressionAttributeNames={"#s": "symbol", "#d": "date", "#c": "close"},
              ExpressionAttributeValues={":s": {"S": sym}}, ProjectionExpression="#d, #c")
    out: dict[str, float] = {}
    while True:
        page = ddb.query(**kw)
        for it in page["Items"]:
            if "close" in it and "N" in it["close"] and float(it["close"]["N"]):    # a zero close is a bad bar
                out[it["date"]["S"]] = float(it["close"]["N"])
        if "LastEvaluatedKey" not in page:
            break
        kw["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    DATA.mkdir(exist_ok=True)
    f.write_text(json.dumps(out))
    return out


def ema(vals, n):
    k = 2.0 / (n + 1)
    o = [vals[0]]
    for v in vals[1:]:
        o.append(v * k + o[-1] * (1 - k))
    return o


def runs(px, bench, gap: int, unit: str, min_len: int, warm: int, merge_cap=None):
    """Completed runs (start_date, end_date, length_days). unit: 'cal' merges dips < gap calendar days, 'ses' < gap sessions."""
    d = [x for x in sorted(set(px) & set(bench)) if x <= CUTOFF]
    if len(d) < 400:
        return []
    rs = [px[x] / bench[x] for x in d]
    tr = ema(rs, EMA_N)
    above = [rs[i] > tr[i] for i in range(len(d))]
    segs, i, n = [], warm, len(d)           # raw above-trend stretches, ignoring the EMA warm-up bars
    while i < n:
        if above[i]:
            j = i
            while j + 1 < n and above[j + 1]:
                j += 1
            segs.append([i, j])
            i = j + 1
        else:
            i += 1
    merged = []
    for s in segs:
        if merged:
            a = merged[-1]
            dip = ((dt.date.fromisoformat(d[s[0]]) - dt.date.fromisoformat(d[a[1]])).days if unit == "cal" else s[0] - a[1] - 1)
            if dip < gap:
                a[1] = s[1]
                continue
        merged.append(s)
    out = []
    for a, b in merged:
        if b >= n - 1:
            continue                         # still running: not a completed run
        ln = (dt.date.fromisoformat(d[b]) - dt.date.fromisoformat(d[a])).days
        if ln >= min_len:
            out.append((d[a], d[b], ln))
    return out


def stats(lengths):
    s = sorted(lengths)
    q = lambda p: s[min(len(s) - 1, int(p * len(s)))]
    return {"n": len(s), "median": st.median(s), "mean": round(st.mean(s)), "p75": q(0.75), "p90": q(0.90)}


def main():
    syms = ["SPY"] + PROXIES_0924
    with cf.ThreadPoolExecutor(8) as ex:
        px = dict(zip(syms, ex.map(load, syms)))
    bench = px.pop("SPY")
    print("published :", PUBLISHED)
    best = None
    for unit in ("cal", "ses"):
        for gap in (14, 15, 16):
            for min_len in (19, 20, 21):
                for warm in (0, 200):
                    L = [r[2] for s in px for r in runs(px[s], bench, gap, unit, min_len, warm)]
                    if not L:
                        continue
                    r = stats(L)
                    err = sum(abs(r[k] - PUBLISHED[k]) / PUBLISHED[k] for k in PUBLISHED)
                    print(f"{unit} gap<{gap} min{min_len} warm{warm}: {r}  err={err:.3f}")
                    if best is None or err < best[0]:
                        best = (err, unit, gap, min_len, warm, r)
    print("closest   :", best)


if __name__ == "__main__":
    main()
