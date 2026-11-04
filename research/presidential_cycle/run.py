"""run.py -- presidential_cycle on real history. check_harness.py must print SELFTEST OK first."""
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "election_cycle"))
import bisect
import numpy as np
import election_study as S
import elections_pres as P

HERE = pathlib.Path(__file__).resolve().parent
rng = np.random.default_rng(20261104)
dates, c = S.load_spx()
V = S.vol20(c)
T = S.expanding_terciles(V)
FIRST = int(np.searchsorted(np.array(dates), "1950-01-01"))
FWD = {h: S.forward(c, h) for h in (21, 63, 126, 252)}
res = {"bars": len(c), "first": dates[0], "last": dates[-1]}

# cross-check: 19 pre-election closes (this study's TradingView file) + the last 300 bars (election_cycle's, same price file)
tv_e = json.loads((HERE / "data/tv_election_checks.json").read_text())
tv_l = json.loads((HERE.parent / "election_cycle/data/tv_last300_closes.json").read_text())
res["crosscheck"] = S.crosscheck(dates, c, tv_e, tv_l)
print(f"cross-check vs TradingView: {res['crosscheck']['checked']} closes, gaps over 0.1%: {len(res['crosscheck']['gaps'])}")

reg = json.loads((HERE.parent / "election_cycle/data/regime_history.json").read_text())
def regime_at(series, day):
    ds = [d for d, _ in series]
    i = bisect.bisect_right(ds, day) - 1
    return series[i][1] if i >= 0 else None

ev = []
for y in P.YEARS:
    d = str(P.DATES[y]); i = S.bar_before(dates, d)
    r6 = float(c[i] / c[i - 126] - 1)
    row = {"year": y, "election": d, "start_bar": dates[i], "i": i, "ret6m": r6,
           "state6": "Up" if r6 >= 0.03 else ("Down" if r6 <= -0.03 else "Flat"),
           "vol20": float(V[i]), "tercile": int(T[i]), "react": float(c[i + 1] / c[i] - 1)}
    for h in FWD: row[f"r{h}"] = float(FWD[h][i])
    a, b, o = (S.bar_before(dates, f"{y}-02-01"), S.bar_before(dates, f"{y}-07-01"), S.bar_before(dates, f"{y}-11-01"))
    seg = c[a:b + 1]
    _, _, msr, msd = S.season_stats(dates, c, y)   # Mar-Sep, descriptive only (not a pre-registered test here)
    row.update({"marsep_ret": msr, "marsep_dd": msd, "janjun_ret": float(c[b] / c[a] - 1), "janjun_dd": float((seg / np.maximum.accumulate(seg) - 1).min()),
                "julopt_ret": float(c[o] / c[b] - 1)})
    row.update(P.facts(y)); row["compass"] = regime_at(reg["compass"], d); row["grid"] = regime_at(reg["grid"], d); ev.append(row)
idx = np.array([r["i"] for r in ev]); terc = np.array([r["tercile"] for r in ev])
mask = S.pool_mask(FWD[252], T, idx, FIRST)
for r in ev:
    r["baseline252"] = float(FWD[252][mask & (T == r["tercile"])].mean()); r["excess252"] = r["r252"] - r["baseline252"]
res["events"] = ev

print("\n== PRIMARY A: 252-bar return from the close before Election Day vs tercile-matched baseline")
res["primary"] = S.excess_test([r["r252"] for r in ev], terc, idx, T, FWD[252], rng, first=FIRST); p = res["primary"]
print(f"   n={p['n']} event {p['mean_event']*100:+.1f}%  baseline {p['mean_baseline']*100:+.1f}%  excess {p['mean_excess']*100:+.1f} pts  p={p['p']:.3f}  "
      f"CI [{p['ci95'][0]*100:+.1f}, {p['ci95'][1]*100:+.1f}]  claim={p['claim']}")
res["secondary"] = {}
for h in (21, 63, 126):
    r = S.excess_test([x[f"r{h}"] for x in ev], terc, idx, T, FWD[h], rng, first=FIRST); res["secondary"][f"post_{h}"] = r
    print(f"   +{h:3d} bars: excess {r['mean_excess']*100:+5.1f} pts  p={r['p']:.3f}  CI [{r['ci95'][0]*100:+.1f}, {r['ci95'][1]*100:+.1f}]  claim={r['claim']}")

print("\n== PRIMARY B / secondary B: season returns, presidential years vs other years 1950-2024 (label permutation)")
allyrs = list(range(1950, 2025)); res["season"] = {}
def seas(y):
    a, b, o = (S.bar_before(dates, f"{y}-02-01"), S.bar_before(dates, f"{y}-07-01"), S.bar_before(dates, f"{y}-11-01"))
    seg = c[a:b + 1]
    return {"janjun_ret": c[b] / c[a] - 1, "julopt_ret": c[o] / c[b] - 1, "janjun_dd": (seg / np.maximum.accumulate(seg) - 1).min()}
SE = {y: seas(y) for y in allyrs}
for k in ("janjun_ret", "julopt_ret", "janjun_dd"):
    a = [SE[y][k] for y in P.YEARS]; b = [SE[y][k] for y in allyrs if y not in P.YEARS]
    d, pv = S.diff_perm(a, b, rng)
    res["season"][k] = {"pres_mean": float(np.mean(a)), "other_mean": float(np.mean(b)), "diff": d, "p": pv, "n_pres": len(a), "n_other": len(b)}
    print(f"   {k:11}: presidential {np.mean(a)*100:+5.1f}%  other {np.mean(b)*100:+5.1f}%  diff {d*100:+5.1f} pts  p={pv:.3f}")

print("\n== EXPLORATORY groupings (descriptive)")
def grp(name, key, order):
    out = {}
    for g in order:
        s = [r for r in ev if r[key] == g]
        out[str(g)] = {"n": len(s), "years": [r["year"] for r in s], "excess252": float(np.mean([r["excess252"] for r in s])) if s else None,
                       "r252": float(np.mean([r["r252"] for r in s])) if s else None, "react": float(np.mean([r["react"] for r in s])) if s else None,
                       "janjun_ret": float(np.mean([r["janjun_ret"] for r in s])) if s else None}
        print(f"   {name:15} {str(g):5} n={len(s):2} 12m excess {out[str(g)]['excess252']*100:+5.1f}  react {out[str(g)]['react']*100:+5.2f}%  Jan-Jun {out[str(g)]['janjun_ret']*100:+5.1f}%")
    res.setdefault("groups", {})[name] = out
grp("winner", "winner", ("D", "R")); grp("party_change", "party_change", (True, False))
grp("incumbent_ran", "incumbent_ran", (True, False)); grp("state6", "state6", ("Down", "Flat", "Up"))
# winner's-party gap (exploratory): plain two-sample standard error (ignores the overlap between neighbouring 12-month windows)
# and leave-one-out influence of each election on the gap
def _gap(es):
    return np.mean([e["excess252"] for e in es if e["winner"] == "D"]) - np.mean([e["excess252"] for e in es if e["winner"] == "R"])
_d = [e["excess252"] for e in ev if e["winner"] == "D"]; _r = [e["excess252"] for e in ev if e["winner"] == "R"]
_se = float(np.sqrt(np.var(_d, ddof=1) / len(_d) + np.var(_r, ddof=1) / len(_r)))
_loo = sorted(((abs(_gap(ev) - _gap([x for x in ev if x is not e])), e["year"]) for e in ev), reverse=True)
res["winner_gap"] = {"gap": float(_gap(ev)), "se": _se, "t": float(_gap(ev) / _se),
                     "loo_largest_shift": [{"year": y, "shift": float(v)} for v, y in _loo[:3]],
                     "loo_gap_range": [float(min(_gap([x for x in ev if x is not e]) for e in ev)), float(max(_gap([x for x in ev if x is not e]) for e in ev))]}
print(f"   winner gap D-R {res['winner_gap']['gap']*100:+.1f} pts, SE {_se*100:.1f} (ignores overlap), t={res['winner_gap']['t']:.2f}; "
      f"dropping any one election the gap stays {res['winner_gap']['loo_gap_range'][0]*100:.1f} to {res['winner_gap']['loo_gap_range'][1]*100:.1f}; "
      f"largest single-year shifts {[(x['year'], round(x['shift']*100, 1)) for x in res['winner_gap']['loo_largest_shift']]}")
res["react_all"] = {"mean": float(np.mean([r["react"] for r in ev])), "up": int(sum(r["react"] > 0 for r in ev)), "n": len(ev)}
print(f"   day after vote: mean {res['react_all']['mean']*100:+.2f}%, up {res['react_all']['up']}/{len(ev)}")
print("\n== per election")
for r in ev:
    print(f"   {r['year']} {r['winner']} {'chg ' if r['party_change'] else 'held'} {'inc ran' if r['incumbent_ran'] else 'open   '} 6m {r['ret6m']*100:+5.1f}% T{r['tercile']} "
          f"react {r['react']*100:+5.2f}% 12m {r['r252']*100:+6.1f}% base {r['baseline252']*100:+5.1f}% excess {r['excess252']*100:+6.1f} JanJun {r['janjun_ret']*100:+5.1f}%")
(HERE / "results.json").write_text(json.dumps(res, indent=1))
