"""run.py -- best/worst-20 out-of-sample check on the real occurrence blob (read-only from S3)."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "api"))
import backtest_data as bd  # noqa: E402
import study  # noqa: E402

blob = bd._read_blob()
tickers = {t: e for t, e in blob["tickers"].items() if t not in bd.RETIRED_TICKERS} if hasattr(bd, "RETIRED_TICKERS") else blob["tickers"]
res = study.run(tickers)
s = res["summary"]
print(f"episodes scored: {s['episodes_scored']}")
for m in ("RAW", "SHRUNK", "EDGE"):
    sp, ic = s[m]["spread_pct"], s[m]["rank_ic"]
    print(f"  {m:6s} top20-bottom20 next episode: {sp['mean']:+.2f} pts  95% CI [{sp['ci95'][0]:+.2f}, {sp['ci95'][1]:+.2f}]"
          f"  positive in {sp['share_positive']*100:.0f}% of episodes | rank IC {ic['mean']:+.3f} [{ic['ci95'][0]:+.3f}, {ic['ci95'][1]:+.3f}]")
for k in ("SHRUNK_minus_RAW", "RAW_minus_EDGE"):
    b = s[k]; print(f"  {k}: {b['mean']:+.2f} pts  95% CI [{b['ci95'][0]:+.2f}, {b['ci95'][1]:+.2f}]")
(pathlib.Path(__file__).resolve().parent / "results.json").write_text(json.dumps(s, indent=1))
