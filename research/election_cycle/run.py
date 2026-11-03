"""run.py -- the election-cycle study on real history. Run check_harness.py first (must print SELFTEST OK), then fetch_data.py."""
import bisect, json, pathlib
import numpy as np
import election_study as S
import elections as E

HERE = pathlib.Path(__file__).resolve().parent
rng = np.random.default_rng(20261104)
dates, c = S.load_spx()
V = S.vol20(c)
T = S.expanding_terciles(V)
FIRST = int(np.searchsorted(np.array(dates), "1950-01-01"))
FWD = {h: S.forward(c, h) for h in (21, 63, 126, 252)}
res = {"bars": len(c), "first": dates[0], "last": dates[-1]}
print(f"SPX closes {len(c)} bars {dates[0]} -> {dates[-1]} (Saturdays before 1952-06-01 dropped; 3 Nov 2026 intraday bar excluded)")

# ---- price cross-check ---------------------------------------------------------------------------------------------------
tv_e = json.loads((HERE / "data/tv_election_checks.json").read_text())
tv_l = json.loads((HERE / "data/tv_last300_closes.json").read_text())
res["crosscheck"] = S.crosscheck(dates, c, tv_e, tv_l)
print(f"cross-check vs TradingView: {res['crosscheck']['checked']} closes compared, gaps over 0.1%: {len(res['crosscheck']['gaps'])}")
for g in res["crosscheck"]["gaps"]:
    print("   GAP", g)

# ---- regime -------------------------------------------------------------------------------------------------------------
reg = json.loads((HERE / "data/regime_history.json").read_text())
def regime_at(series, day):
    ds = [d for d, _ in series]
    i = bisect.bisect_right(ds, day) - 1
    return series[i][1] if i >= 0 else None

# ---- events -------------------------------------------------------------------------------------------------------------
years = E.MIDTERMS
ev = []
for y in years:
    d = str(E.DATES[y])
    i = S.bar_before(dates, d)
    st, dd, r3 = S.state_at(c, i)
    row = {"year": y, "election": d, "start_bar": dates[i], "i": i, "state": st, "dd52w": float(dd), "ret3m": float(r3),
           "vol20": float(V[i]), "tercile": int(T[i])}
    for h in FWD:
        row[f"r{h}"] = float(FWD[h][i])
    s_i, e_i, sr, sdd = S.season_stats(dates, c, y)
    sst, _, _ = S.state_at(c, s_i)
    row.update({"season_ret": sr, "season_dd": sdd, "season_state": sst})
    row["compass"] = regime_at(reg["compass"], d)
    row["grid"] = regime_at(reg["grid"], d)
    row.update(E.results(y))
    ev.append(row)
idx = np.array([r["i"] for r in ev])
terc = np.array([r["tercile"] for r in ev])
for r in ev:
    mask = S.pool_mask(FWD[252], T, idx, FIRST)
    r["baseline252"] = float(FWD[252][mask & (T == r["tercile"])].mean())
    r["excess252"] = r["r252"] - r["baseline252"]

# ---- primary + secondary ---------------------------------------------------------------------------------------------
print("\n== PRIMARY (stated before running): 252-bar return from the close before election day vs tercile-matched baseline")
res["primary"] = S.excess_test([r["r252"] for r in ev], terc, idx, T, FWD[252], rng, first=FIRST)
p = res["primary"]
print(f"   n={p['n']}  event mean {p['mean_event']*100:+.1f}%  baseline {p['mean_baseline']*100:+.1f}%  excess {p['mean_excess']*100:+.1f} pts  "
      f"p={p['p']:.3f}  95% CI [{p['ci95'][0]*100:+.1f}, {p['ci95'][1]*100:+.1f}]  claim={p['claim']}  pool {p['pool_sizes']}")

print("\n== SECONDARY (6 pre-registered)")
res["secondary"] = {}
for h in (21, 63, 126):
    r = S.excess_test([x[f"r{h}"] for x in ev], terc, idx, T, FWD[h], rng, first=FIRST)
    res["secondary"][f"post_{h}"] = r
    print(f"   post-election +{h:3d} bars: excess {r['mean_excess']*100:+5.1f} pts  p={r['p']:.3f}  CI [{r['ci95'][0]*100:+.1f}, {r['ci95'][1]*100:+.1f}]  claim={r['claim']}")
sub = [k for k, r in enumerate(ev) if r["year"] >= 1994]
r = S.excess_test([ev[k]["r252"] for k in sub], terc[sub], idx[sub], T, FWD[252], rng, first=FIRST)
res["secondary"]["primary_1994_2022"] = r
print(f"   primary on 1994-2022 (n={len(sub)}): excess {r['mean_excess']*100:+5.1f} pts  p={r['p']:.3f}  CI [{r['ci95'][0]*100:+.1f}, {r['ci95'][1]*100:+.1f}]  claim={r['claim']}")

seas = {y: S.season_stats(dates, c, y) for y in range(1950, 2023)}
mid = [seas[y] for y in years]
oth = [seas[y] for y in range(1950, 2023) if y not in years]
res["season"] = {}
for name, k in (("return", 2), ("max_drawdown", 3)):
    d, pv = S.diff_perm([m[k] for m in mid], [o[k] for o in oth], rng)
    res["season"][name] = {"midterm_mean": float(np.mean([m[k] for m in mid])), "other_mean": float(np.mean([o[k] for o in oth])),
                           "diff": d, "p": pv, "n_mid": len(mid), "n_other": len(oth)}
    print(f"   Mar1-Sep30 {name:12}: midterm years {np.mean([m[k] for m in mid])*100:+5.1f}%  other {np.mean([o[k] for o in oth])*100:+5.1f}%  "
          f"diff {d*100:+5.1f} pts  p={pv:.3f}")

# ---- exploratory ----------------------------------------------------------------------------------------------------------
print("\n== EXPLORATORY (descriptive, not tests)")
res["explore_state"] = {}
for st in ("Correction", "Flat", "Up"):
    a = [r for r in ev if r["state"] == st]
    b = [r for r in ev if r["season_state"] == st]
    res["explore_state"][st] = {"n_pre_election": len(a), "post12m_excess_mean": float(np.mean([r["excess252"] for r in a])) if a else None,
                                "n_season": len(b), "season_ret_mean": float(np.mean([r["season_ret"] for r in b])) if b else None}
    print(f"   {st:10} pre-election n={len(a):2} mean 12m excess {res['explore_state'][st]['post12m_excess_mean']}   |  end-Feb n={len(b):2} season ret {res['explore_state'][st]['season_ret_mean']}")
flags = {"pres_party_lost_>=20_house_seats": lambda r: r["pres_house_seat_change"] <= -20, "pres_party_lacks_house_majority": lambda r: r["pres_lost_house"],
         "pres_party_lacks_senate_majority": lambda r: r["pres_lost_senate"], "divided_government_after": lambda r: r["divided_after"]}
res["explore_politics"] = {}
for fk, fn in flags.items():
    for tk, tn in (("post12m_excess", "excess252"), ("season_ret", "season_ret")):
        a = [r[tn] for r in ev if fn(r)]; b = [r[tn] for r in ev if not fn(r)]
        res["explore_politics"][f"{fk}|{tk}"] = {"n_yes": len(a), "mean_yes": float(np.mean(a)) if a else None, "n_no": len(b), "mean_no": float(np.mean(b)) if b else None}
        if a and b:
            print(f"   {fk:34} {tk:15} yes n={len(a):2} {np.mean(a)*100:+5.1f}%   no n={len(b):2} {np.mean(b)*100:+5.1f}%")

# ---- live case ------------------------------------------------------------------------------------------------------------
li = len(c) - 1
st, dd, r3 = S.state_at(c, li)
res["live_2026"] = {"close_date": dates[li], "close": float(c[li]), "state": st, "dd52w": float(dd), "ret3m": float(r3),
                    "vol20": float(V[li]), "tercile": int(T[li]), "baseline252_for_tercile": float(FWD[252][S.pool_mask(FWD[252], T, idx, FIRST) & (T == T[li])].mean()),
                    "compass_hist": regime_at(reg["compass"], dates[li]), "grid_hist": regime_at(reg["grid"], dates[li])}
print(f"\n== LIVE 2026 (not counted): close {dates[li]} {c[li]:.2f}  state {st} (drawdown {dd*100:.1f}%, 3m {r3*100:+.1f}%), vol tercile {T[li]}, regime table C{res['live_2026']['compass_hist']}G{res['live_2026']['grid_hist']}")
res["events"] = ev
(HERE / "results.json").write_text(json.dumps(res, indent=1, default=float))
print("\n== per-midterm table")
for r in ev:
    print(f"   {r['year']} {r['state']:10} T{r['tercile']} 12m {r['r252']*100:+6.1f}%  base {r['baseline252']*100:+5.1f}%  excess {r['excess252']*100:+6.1f}  season {r['season_ret']*100:+6.1f}% dd {r['season_dd']*100:6.1f}%  C{r['compass']}G{r['grid']}")
