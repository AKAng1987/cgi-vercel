"""run.py -- COT extremes vs price on CGI's instruments (CFTC public API + price-history, read-only)."""
import json, pathlib, sys
import numpy as np, pandas as pd, boto3

API = pathlib.Path(__file__).resolve().parents[2] / "api"
sys.path.insert(0, str(API))
import cot_data  # noqa: E402
import study  # noqa: E402

# contract label -> (price symbol, sign): sign +1 when the contract's long side profits from the price rising.
# FX futures are quoted against USD in CGI (USDJPY etc.), so a long-yen crowd profits when USDJPY FALLS.
MAP = {
    "Natural Gas": ("NATGAS", 1), "Crude Oil": ("USOIL", 1), "Gold": ("XAUUSD", 1), "Silver": ("SILVER", 1),
    "Copper": ("COPPER", 1), "Corn": ("CORN", 1), "Soybeans": ("SOYB", 1), "Wheat": ("WEAT", 1),
    "Sugar": ("CANE", 1), "Cotton": ("COTTON", 1),
    "2-Year Note": ("SHY", 1), "10-Year Note": ("IEF", 1), "30-Year Bond": ("TLT", 1),
    "US Dollar Index": ("UUP", 1), "Euro FX": ("USDEUR", -1), "Japanese Yen": ("USDJPY", -1),
    "British Pound": ("USDGBP", -1), "Canadian Dollar": ("USDCAD", -1), "Swiss Franc": ("USDCHF", -1),
    "Australian Dollar": ("USDAUD", -1), "Mexican Peso": ("USDMXN", -1),
    "S&P 500 (E-mini)": ("SPX", 1), "Nasdaq 100 (E-mini)": ("IXIC", 1), "Russell 2000 (E-mini)": ("RUT", 1),
    "Dow (x $5)": ("DJI", 1), "VIX": ("VIX", 1), "Bitcoin": ("BTC", 1),
}
names = {lab: nm for grp in cot_data.CONTRACTS.values() for lab, nm in grp}
ddb = boto3.client("dynamodb", region_name="ap-southeast-1")


def prices(sym):
    rows, kw = [], dict(TableName="cmon-stage-backend-price-history", KeyConditionExpression="symbol = :s",
                        ExpressionAttributeValues={":s": {"S": sym}}, ExpressionAttributeNames={"#d": "date", "#c": "close"},
                        ProjectionExpression="#d, #c, high, low")
    while True:
        r = ddb.query(**kw)
        for it in r["Items"]:
            g = lambda k: float(it[k]["N"]) if k in it and "N" in it[k] else np.nan
            rows.append((it["date"]["S"], g("close"), g("high"), g("low")))
        if "LastEvaluatedKey" not in r:
            break
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]
    df = pd.DataFrame(rows, columns=["date", "close", "high", "low"]).set_index("date").sort_index()
    df.index = pd.to_datetime(df.index)
    df = df[df.index.dayofweek < 5] if sym != "BTC" else df
    return df[df.index >= "2003-01-01"]


all_ev, all_brk, rand = [], [], []
for lab, (sym, sign) in MAP.items():
    s = cot_data._series(names[lab])
    spec = pd.Series([x["spec"] for x in s], index=pd.to_datetime([x["date"] for x in s])).sort_index()
    spec = spec[~spec.index.duplicated()]
    ev = study.events(study.cot_index(spec))
    px = prices(sym)
    if len(px) < 300:
        print(f"skip {lab}: no prices"); continue
    ev = ev[(ev.index > px.index[0] + pd.Timedelta(days=60))]
    rows = study.analyse(px, ev, sign)
    for r in rows: r["contract"] = lab
    all_ev += rows
    all_brk += study.breakout_baseline(px)
    rand.append(study.random_turn_baseline(px["close"], n=150, seed=len(rand)))
    print(f"{lab:22s} {sym:7s} events {len(rows):3d}")

E, B = pd.DataFrame(all_ev), pd.DataFrame(all_brk)
R = np.concatenate(rand)
out = {"n_events": len(E), "contracts": int(E["contract"].nunique())}
print(f"\n{len(E)} extreme episodes across {E['contract'].nunique()} contracts")

turned = E["days_to_turn"].notna()
r_turn = ~np.isnan(R)
out["turn"] = {"share_within_13w": float(turned.mean()), "median_days": float(E["days_to_turn"].median()),
               "random_share_within_13w": float(r_turn.mean()), "random_median_days": float(np.nanmedian(R))}
print(f"turned (4-week breakout against the crowd) within 13 weeks: {turned.mean()*100:.0f}% "
      f"(median {E['days_to_turn'].median():.0f} days) vs random dates {r_turn.mean()*100:.0f}% (median {np.nanmedian(R):.0f} days)")

print("\nforward return AGAINST the crowd, demeaned (%), 95% CI over event weeks")
for h in study.HORIZONS:
    a = study.week_boot(E, f"ev_{h}"); c = study.week_boot(E, f"conf_{h}"); b = study.week_boot(B, f"brk_{h}")
    out[f"h{h}"] = {"event": a, "confirmed": c, "breakout_alone": b}
    print(f"  {h:2d}d  at report {a['mean']*100:+.2f} [{a['ci95'][0]*100:+.2f},{a['ci95'][1]*100:+.2f}] n={a['n']}"
          f" | after confirmation {c['mean']*100:+.2f} [{c['ci95'][0]*100:+.2f},{c['ci95'][1]*100:+.2f}] n={c['n']}"
          f" | any breakout {b['mean']*100:+.2f} [{b['ci95'][0]*100:+.2f},{b['ci95'][1]*100:+.2f}] n={b['n']}")

print("\nsplits at the report (40d against-crowd return, share turned within 13w)")
E["adx_b"] = pd.cut(E["adx"], [0, 20, 30, 200], labels=["ADX<20", "ADX20-30", "ADX>30"])
E["atr_b"] = pd.cut(E["atr_rel"], [0, 0.8, 1.25, 50], labels=["ATR% low", "ATR% normal", "ATR% high"])
E["side"] = E["crowd"].map({1: "crowded long", -1: "crowded short"})
E["era"] = np.where(pd.to_datetime(E["date"]) < "2016-01-01", "2006-15", "2016-26")
splits, pvals = {}, []
for col in ("adx_b", "atr_b", "side", "era"):
    for k, g in E.groupby(col, observed=True):
        b = study.week_boot(g, "ev_40", reps=1000)
        v = g["ev_40"].dropna().to_numpy()
        p = float(min(1, 2 * min((v <= 0).mean(), (v >= 0).mean()))) if len(v) else 1.0
        ttr = g["days_to_turn"].notna().mean()
        splits[f"{col}:{k}"] = {**b, "turned_13w": float(ttr), "p_sign": p}
        pvals.append((f"{col}:{k}", b))
        print(f"  {str(k):14s} 40d {b['mean']*100:+.2f} [{b['ci95'][0]*100:+.2f},{b['ci95'][1]*100:+.2f}] n={b['n']}  turned {ttr*100:.0f}%")
out["splits"] = splits
(pathlib.Path(__file__).resolve().parent / "results.json").write_text(json.dumps(out, indent=1, default=float))
E.to_csv(pathlib.Path(__file__).resolve().parent / "events.csv", index=False)
