"""run.py -- the pre-registered tests (PREREG.md) on real data. Run check_harness.py first; it must print SELFTEST OK."""
import json, pathlib
import numpy as np
import study as S

HERE = pathlib.Path(__file__).resolve().parent
rng = np.random.default_rng(20261105)
dates, rets = S.load()
bucket, quad = S.labels(dates, 1)
b21, _ = S.labels(dates, 21)
days, W = S.schedule(rets, dates, bucket, quad)
_, W21 = S.schedule(rets, dates, bucket, quad, lag_bucket=b21)
R, TURN, GROSS = {}, {}, {}
for k in W:
    R[k], TURN[k] = S.simulate(rets, days, W[k])
    GROSS[k], _ = S.simulate(rets, days, W[k], costs=np.zeros(rets.shape[1]))
R["C1lag21"], _ = S.simulate(rets, days, W21["C1"])
t0 = days[0]
rf = rets[t0:, S.SLEEVES.index("SHY")]
T = len(rf)
idx = S.block_idx(T, 2000, rng)
print(f"scored {dates[t0]} -> {dates[-1]}: {T} days, {len(days)} monthly decisions")

def desc(r):
    return dict(ret=float(S.ann_ret(r)), vol=float(S.ann_vol(r)), sharpe=float(S.sharpe(r, rf)), maxdd=float(S.maxdd(r)), calmar=float(S.calmar(r)))
table = {k: desc(R[k]) for k in ("B1", "B2", "B3", "B4", "B5", "C1", "C1rp", "C1q", "C1pure", "B4roll", "C1lag21")}
for k in table:
    table[k]["turnover_per_month"] = float(TURN[k][1:].mean()) if k in TURN else None
    table[k]["cost_drag_pa"] = float(S.ann_ret(GROSS[k]) - S.ann_ret(R[k])) if k in GROSS else None
print("\nportfolio  ret    vol    sharpe maxDD  calmar turn/mo")
for k, v in table.items():
    print(f"{k:8} {v['ret']*100:5.2f}% {v['vol']*100:5.2f}% {v['sharpe']:6.2f} {v['maxdd']*100:5.1f}% {v['calmar']:5.2f} {v['turnover_per_month'] if v['turnover_per_month'] is not None else float('nan'):.2f}")

res = {"scored": [dates[t0], dates[-1]], "days": T, "decisions": len(days), "table": table}
# ---- primary
ok, a, b = S.primary_claim(R, idx, "vol")
res["primary"] = {"vs_B3": a, "vs_B4": b, "claim": bool(ok), "note": "annual volatility, benchmark minus C1 (positive = C1 calmer); PREREG Amendment 1"}
print(f"\nPRIMARY annual volatility (benchmark minus C1, pts): vs B3 {a[0]*100:+.2f} [{a[1]*100:+.2f}, {a[2]*100:+.2f}]   vs B4 {b[0]*100:+.2f} [{b[1]*100:+.2f}, {b[2]*100:+.2f}]   CLAIM: {ok}")
# ---- secondary (vs B3; B4 shown for context)
sec = {}
for name, fn, sign, needs_rf in (("maxdd", S.maxdd, -1, False), ("sharpe", S.sharpe, 1, True), ("calmar", S.calmar, 1, False)):
    out = {}
    for base in ("B3", "B4"):
        pt, lo, hi = S.paired(R["C1"], R[base], fn, idx, rf=rf if needs_rf else None)
        pt, lo, hi = (pt, lo, hi) if sign > 0 else (-pt, -hi, -lo)       # positive = C1 better
        out[base] = (pt, lo, hi)
    sec[name] = {"vs_B3": out["B3"], "vs_B4": out["B4"], "claim": bool(out["B3"][1] > 0)}
    print(f"SECONDARY {name:6} C1 better by: vs B3 {out['B3'][0]:+.4f} [{out['B3'][1]:+.4f}, {out['B3'][2]:+.4f}] claim={sec[name]['claim']}   vs B4 {out['B4'][0]:+.4f} [{out['B4'][1]:+.4f}, {out['B4'][2]:+.4f}]")
res["secondary"] = sec
ret_d = {b_: S.paired(R["C1"], R[b_], S.ann_ret, idx) for b_ in ("B3", "B4")}
res["return_descriptive"] = ret_d
print("RETURN (descriptive, C1 minus base, annual):", {k: f"{v[0]*100:+.2f} [{v[1]*100:+.2f}, {v[2]*100:+.2f}]" for k, v in ret_d.items()})
# ---- exploratory (13)
ex = {}
def dd_test(label, better, worse, i=idx):
    pt, lo, hi = S.claim_dd(better, worse, i); ex[label] = dict(diff=pt, lo=lo, hi=hi, claim=bool(lo > 0)); print(f"  {label:44} {pt*100:+6.2f} [{lo*100:+6.2f}, {hi*100:+6.2f}]  {'CLAIM' if lo > 0 else ''}")
print("\nEXPLORATORY max drawdown, benchmark minus candidate (pts):")
dd_test("E1 C1 vs B1 equal weight", R["C1"], R["B1"]); dd_test("E2 C1 vs B2 60/40", R["C1"], R["B2"]); dd_test("E3 C1 vs B5 risk parity", R["C1"], R["B5"])
dd_test("E4 regime risk parity vs B5", R["C1rp"], R["B5"]); dd_test("E5 16-quadrant R (C1q) vs B4", R["C1q"], R["B4"]); dd_test("E6 pure regime R (C1pure) vs B4", R["C1pure"], R["B4"])
dd_test("E7 21-day label lag, C1 vs B4", R["C1lag21"], R["B4"])
dts = np.array(dates[t0:])
for nm, lo_, hi_ in (("E8 2010-2015", "2010", "2016"), ("E9 2016-2020", "2016", "2021"), ("E10 2021-2026", "2021", "2027")):
    m = (np.array([d[:4] for d in dts]) >= lo_) & (np.array([d[:4] for d in dts]) < hi_)
    i2 = S.block_idx(int(m.sum()), 2000, rng)
    dd_test(nm + ", C1 vs B4", R["C1"][m], R["B4"][m], i2)
dd_test("E11 C1 vs rolling-756 blind min-var", R["C1"], R["B4roll"])
dd_test("E12 vol-matched (10%) C1 vs B3", S.scale_to_vol(R["C1"]), S.scale_to_vol(R["B3"]))
# E13 ENB lead
ew = rets.mean(axis=1)
dec = days
enbs, tgt, v20 = [], [], []
for i in dec:
    if i + 63 >= len(rets) or i < 252: continue
    enbs.append(S.enb(np.corrcoef(rets[i - 252:i], rowvar=False))); v20.append(rets[i - 20:i].mean(axis=1).std())
    e = np.cumprod(1 + ew[i:i + 63]); tgt.append((1 - e / np.maximum.accumulate(e)).max())
rk = lambda x: np.argsort(np.argsort(x)).astype(float)
def partial(e_, t_, v_):
    e_, t_, v_ = rk(e_), rk(t_), rk(v_)
    res_ = lambda y: y - np.polyval(np.polyfit(v_, y, 1), v_)
    return float(np.corrcoef(res_(e_), res_(t_))[0, 1])
enbs, tgt, v20 = map(np.array, (enbs, tgt, v20))
pt = partial(enbs, tgt, v20); n = len(enbs); bs = []
for _ in range(2000):
    st = rng.integers(0, n - 3, size=int(np.ceil(n / 3))); ii = (st[:, None] + np.arange(3)).ravel()[:n]
    bs.append(partial(enbs[ii], tgt[ii], v20[ii]))
lo, hi = np.percentile(bs, [2.5, 97.5])
ex["E13 ENB vs next-63d EW drawdown (partial on vol20)"] = dict(rho=pt, lo=float(lo), hi=float(hi), n=n, claim=bool(lo > 0 or hi < 0))
print(f"  E13 ENB vs next-63d EW drawdown, partial on vol20: rho {pt:+.3f} [{lo:+.3f}, {hi:+.3f}] n={n}  {'CLAIM' if lo > 0 or hi < 0 else ''}")
res["exploratory"] = ex
print(f"exploratory claims: {sum(v['claim'] for v in ex.values())} of {len(ex)}; expected by chance about {0.05*len(ex):.1f}")
# ---- descriptive correlations and stability
names = S.SLEEVES
off = lambda m: m[np.triu_indices(len(m), 1)]
cb = {k: np.corrcoef(rets[(bucket == k)], rowvar=False) for k in (1, 2, 3)}
cb["all"] = np.corrcoef(rets, rowvar=False)
pairs = [("SPY", "TLT"), ("SPY", "IEF"), ("SPY", "GLD"), ("SPY", "DBC"), ("SPY", "UUP"), ("SPY", "VNQ"), ("SPY", "EWJ"), ("TLT", "GLD")]
ix = lambda s: names.index(s)
desc_c = {f"{a_}-{b_}": {str(k): float(m[ix(a_), ix(b_)]) for k, m in cb.items()} for a_, b_ in pairs}
print("\nCORRELATION by Compass bucket (1, 2, 3 = C3+C4, all):"); [print(f"  {p:10}", {k: round(v, 2) for k, v in d.items()}) for p, d in desc_c.items()]
eras = [("2007", "2013"), ("2013", "2019"), ("2019", "2027")]
ar = np.array([d[:4] for d in dates])
em = [np.corrcoef(rets[(ar >= a_) & (ar < b_)], rowvar=False) for a_, b_ in eras]
era_stab = [float(np.corrcoef(off(em[i]), off(em[j]))[0, 1]) for i, j in ((0, 1), (1, 2), (0, 2))]
reg_stab = {f"{i}v{j}": float(np.corrcoef(off(cb[i]), off(cb[j]))[0, 1]) for i, j in ((1, 2), (1, 3), (2, 3))}
reg_vs_all = {str(k): float(np.corrcoef(off(cb[k]), off(cb["all"]))[0, 1]) for k in (1, 2, 3)}
mad = {str(k): float(np.abs(off(cb[k]) - off(cb["all"])).mean()) for k in (1, 2, 3)}
era_mad = [float(np.abs(off(em[i]) - off(em[j])).mean()) for i, j in ((0, 1), (1, 2), (0, 2))]
print(f"STABILITY: era-to-era matrix correlation {np.round(era_stab, 2)} (mean abs gap {np.round(era_mad, 3)}); bucket-to-bucket {reg_stab}; bucket vs all {reg_vs_all} (mean abs gap {mad})")
ew_w = np.full(len(names), 1 / len(names)); vol_all = rets.std(axis=0)
dr = {str(k): S.div_ratio(ew_w, rets[bucket == k].std(axis=0), cb[k]) for k in (1, 2, 3, "all")}
dr["all"] = S.div_ratio(ew_w, vol_all, cb["all"])
en = {str(k): S.enb(cb[k]) for k in cb}
print("DIVERSIFICATION RATIO (equal weight):", {k: round(v, 2) for k, v in dr.items()}, " ENB:", {k: round(v, 2) for k, v in en.items()})
res["descriptive"] = dict(corr=desc_c, era_stability=era_stab, era_mad=era_mad, bucket_stability=reg_stab, bucket_vs_all=reg_vs_all, bucket_mad=mad, div_ratio=dr, enb=en,
                          bucket_days={str(k): int((bucket == k).sum()) for k in (1, 2, 3)})
(HERE / "results.json").write_text(json.dumps(res, indent=1, default=float))
