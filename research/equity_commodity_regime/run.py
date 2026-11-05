"""run.py -- the pre-registered tests (PREREG.md and Amendment 1) on real data. Run check_harness.py first; it must print SELFTEST OK."""
import json, pathlib
import numpy as np
import study as S

D = S.D
HERE = pathlib.Path(__file__).resolve().parent
rng = np.random.default_rng(20261105)
dates, rets = S.load()
bucket, quad = S.labels(dates, 1)
b21, _ = S.labels(dates, 21)
days, W = S.schedule(rets, dates, bucket, quad, lag_bucket=b21)
R, TURN, GROSS = {}, {}, {}
for k in W:
    R[k], TURN[k] = S.simulate(rets, days, W[k])
    GROSS[k], _ = S.simulate(rets, days, W[k], costs=np.zeros(rets.shape[1]))
t0 = days[0]; rf = rets[t0:, S.CASH]; T = len(rf)
idx = D.block_idx(T, 2000, rng)
print(f"scored {dates[t0]} -> {dates[-1]}: {T} days, {len(days)} monthly decisions")
desc = lambda r: dict(ret=float(D.ann_ret(r)), vol=float(D.ann_vol(r)), sharpe=float(D.sharpe(r, rf)), maxdd=float(D.maxdd(r)), calmar=float(D.calmar(r)))
table = {k: desc(R[k]) for k in R}
for k in table:
    table[k]["turnover_per_month"] = float(TURN[k][1:].mean()); table[k]["cost_drag_pa"] = float(D.ann_ret(GROSS[k]) - D.ann_ret(R[k]))
    table[k]["avg_cash"] = float(W[k][:, S.CASH].mean())
print("\nportfolio   ret    vol   sharpe  maxDD  calmar turn/mo  avg cash")
for k, v in table.items():
    print(f"{k:8} {v['ret']*100:5.2f}% {v['vol']*100:5.2f}% {v['sharpe']:6.2f} {v['maxdd']*100:5.1f}% {v['calmar']:5.2f}  {v['turnover_per_month']:.2f}  {v['avg_cash']*100:4.0f}%")
res = {"scored": [dates[t0], dates[-1]], "days": T, "decisions": len(days), "table": table}
P = S.primary(R, rf, idx); res["primary"] = {}
print("\nPRIMARY (97.5% intervals):")
p1 = P["P1"][1]; print(f"  P1 regime tilt, Sharpe T1 - G0: {p1[0]:+.3f} [{p1[1]:+.3f}, {p1[2]:+.3f}]  CLAIM: {P['P1'][0]}")
a, b = P["P3"][1], P["P3"][2]
print(f"  P3 regime correlations, volatility (pts, benchmark minus C): vs B4e {a[0]*100:+.2f} [{a[1]*100:+.2f}, {a[2]*100:+.2f}]   vs V {b[0]*100:+.2f} [{b[1]*100:+.2f}, {b[2]*100:+.2f}]  CLAIM: {P['P3'][0]}")
p2 = P["P2"][1]; print(f"  P2 (descriptive) vol sizing, Sharpe V - EW: {p2[0]:+.3f} [{p2[1]:+.3f}, {p2[2]:+.3f}]")
res["primary"] = {"P1": dict(est=p1, claim=bool(P["P1"][0])), "P3": dict(vs_B4e=a, vs_V=b, claim=bool(P["P3"][0])), "P2_descriptive": p2}
# Sharpe for P3, shown beside it
for base in ("B4e", "V"):
    pt = S.paired_ci(R["C"], R[base], D.sharpe, idx, rf=rf)
    print(f"  (beside P3) Sharpe C - {base}: {pt[0]:+.3f} [{pt[1]:+.3f}, {pt[2]:+.3f}]"); res["primary"][f"P3_sharpe_vs_{base}"] = pt
dd = lambda a_, b_: S.paired_ci(R[b_], R[a_], D.maxdd, idx)       # positive = a_ shallower
cal = lambda a_, b_: S.paired_ci(R[a_], R[b_], D.calmar, idx)
sec = {}
print("\nSECONDARY (95%):")
for nm, f, a_, b_ in (("maxdd T1 vs G0", dd, "T1", "G0"), ("calmar T1 vs G0", cal, "T1", "G0"), ("maxdd C vs B4e", dd, "C", "B4e"), ("calmar C vs B4e", cal, "C", "B4e")):
    v = f(a_, b_); sec[nm] = dict(est=v, claim=bool(v[1] > 0)); print(f"  {nm:18} {v[0]:+.4f} [{v[1]:+.4f}, {v[2]:+.4f}] {'CLAIM' if v[1] > 0 else ''}")
res["secondary"] = sec
res["return_descriptive"] = {k: S.paired_ci(R[a_], R[b_], D.ann_ret, idx) for k, (a_, b_) in {"T1_G0": ("T1", "G0"), "C_B4e": ("C", "B4e")}.items()}
print("RETURN (descriptive, annual):", {k: f"{v[0]*100:+.2f} [{v[1]*100:+.2f}, {v[2]*100:+.2f}]" for k, v in res["return_descriptive"].items()})
ex = {}
print("\nEXPLORATORY Sharpe difference (95%; volatility difference in pts beside C-type tests):")
def sx(label, a_, b_, i=idx, sel=None):
    ra, rb, rff = (R[a_], R[b_], rf) if sel is None else (R[a_][sel], R[b_][sel], rf[sel])
    v = S.paired_ci(ra, rb, D.sharpe, i, rf=rff); vo = S.paired_ci(rb, ra, D.ann_vol, i)
    ex[label] = dict(sharpe=v, vol_pts=vo, claim=bool(v[1] > 0)); print(f"  {label:40} {v[0]:+.3f} [{v[1]:+.3f}, {v[2]:+.3f}]   vol {vo[0]*100:+.2f} [{vo[1]*100:+.2f}, {vo[2]*100:+.2f}]  {'CLAIM' if v[1] > 0 else ''}")
sx("E1 16-quadrant tilt vs G0", "T1q", "G0"); sx("E2 pure-regime R vs B4e", "Cpure", "B4e"); sx("E3 21-day lag tilt vs G0", "T1lag", "G0"); sx("E4 21-day lag C vs B4e", "Clag", "B4e")
yr = np.array([d[:4] for d in dates[t0:]])
for nm, lo_, hi_ in (("E5 C vs B4e 2009-2014", "2009", "2015"), ("E6 C vs B4e 2015-2020", "2015", "2021"), ("E7 C vs B4e 2021-2026", "2021", "2027")):
    m = (yr >= lo_) & (yr < hi_); sx(nm, "C", "B4e", D.block_idx(int(m.sum()), 2000, rng), m)
sx("E8 C vs rolling-756 blind min-var", "C", "B4roll")
res["exploratory"] = ex
print(f"exploratory Sharpe claims: {sum(v['claim'] for v in ex.values())} of {len(ex)}; expected by chance about {0.025*len(ex):.1f}")
# descriptive: group returns and correlation by bucket
r = rets[:, :10]; eqr, cmr = r[:, S.EQ].mean(axis=1), r[:, S.CM].mean(axis=1)
dsc = {}
print("\nDESCRIPTIVE by Compass bucket (days since 2007; equity-minus-commodity annualised, correlation of the two groups):")
for k in (1, 2, 3):
    m = bucket == k
    dsc[str(k)] = dict(days=int(m.sum()), eq_ann=float(eqr[m].mean() * 252), cm_ann=float(cmr[m].mean() * 252), eq_minus_cm=float((eqr[m] - cmr[m]).mean() * 252), corr=float(np.corrcoef(eqr[m], cmr[m])[0, 1]))
    print(f"  bucket {k}: {m.sum()} days  equities {dsc[str(k)]['eq_ann']*100:+.1f}%  commodities {dsc[str(k)]['cm_ann']*100:+.1f}%  gap {dsc[str(k)]['eq_minus_cm']*100:+.1f}%  corr {dsc[str(k)]['corr']:+.2f}")
res["descriptive"] = dsc
wm = {k: dict(zip(S.NAMES, [float(x) for x in W[k].mean(axis=0)])) for k in ("B4e", "C")}
res["avg_weights"] = wm; res["mean_abs_weight_change_C_vs_B4e"] = float(np.abs(W["C"] - W["B4e"]).sum(axis=1).mean())
print("\nAVERAGE WEIGHTS B4e:", {k: round(v, 2) for k, v in wm["B4e"].items()}, " mean |C - B4e| per month (two-sided):", round(res["mean_abs_weight_change_C_vs_B4e"], 3))
(HERE / "results.json").write_text(json.dumps(res, indent=1, default=float))
