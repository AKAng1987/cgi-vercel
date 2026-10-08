"""run.py -- HMM risk state vs plain 20-day vol sizing on real index history (price-history, daily closes)."""
import json, pathlib, sys
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "api"))
import axis_drivers as ad  # noqa: E402
import study  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
START = {"SPX": "1960-01-01", "IXIC": "1971-01-01", "RUT": "1987-09-01"}
res = {}
for sym, start in START.items():
    d, c = ad._load_close(sym)
    keep = [i for i, x in enumerate(d) if x >= start]
    px = np.array([c[i] for i in keep])
    r = px[1:] / px[:-1] - 1
    out = study.run(r)
    res[sym] = out
    print(f"\n=== {sym} from {start}: {out['n_days']} days scored (after a 10y warm-up)")
    for k in ("HOLD", "VOL20", "HMM"):
        s = out[k]
        print(f"  {k:6s} CAGR {s['cagr']*100:5.1f}%  vol {s['vol']*100:4.1f}%  Sharpe {s['sharpe']:.2f}  "
              f"maxDD {s['max_dd']*100:4.1f}%  Calmar {s['calmar']:.2f}")
    b = out["HMM_vs_VOL20"]
    print(f"  HMM - VOL20 Sharpe: {b['diff']:+.3f}  95% CI [{b['ci95'][0]:+.3f}, {b['ci95'][1]:+.3f}]")
(HERE / "results.json").write_text(json.dumps(res, indent=1, default=float))
