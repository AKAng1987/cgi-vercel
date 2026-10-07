"""
check_api_imports.py -- import main.py exactly the way uvicorn does.

WHY THIS EXISTS

Nine consecutive Render deploys failed on `NameError: name 'Body' is not
defined` at main.py import time, and none of it was visible locally. Every
individual module imported fine, every build passed, every test passed --
because nothing ever imported `main` itself. uvicorn does, and that is the
only import that decides whether the service starts.

The cause was a revert: `Body` was added to the fastapi import for a feature
that was later backed out with `git checkout`, which removed the import
while a later commit still used the name.

python-dotenv is stubbed because it is a Render dependency, not a local one;
everything else is imported for real, so a missing name, a circular import
or a bad decorator signature fails here instead of in production.

    python3 scripts/check_api_imports.py

If the interpreter running this has no fastapi, it re-runs itself under
api/.venv. Without that, a bare `python3` fails on the missing package and
the failure reads as "check broken", not "check not run" -- which is how it
got ignored once.
"""
from __future__ import annotations

import pathlib
import sys
import types

API = pathlib.Path(__file__).resolve().parent.parent / "api"

try:
    import fastapi  # noqa: F401
except ModuleNotFoundError:
    import os
    venv_py = API / ".venv" / "bin" / "python"
    # A venv's python is a symlink to the system one, so comparing resolved
    # paths cannot tell them apart -- use a flag to avoid an exec loop.
    if venv_py.exists() and not os.environ.get("_CGI_IMPORT_CHECK_REEXEC"):
        os.environ["_CGI_IMPORT_CHECK_REEXEC"] = "1"
        os.execv(str(venv_py), [str(venv_py), __file__, *sys.argv[1:]])
    sys.exit("FAIL: fastapi is not installed and api/.venv was not found -- "
             "this check did NOT run, which is different from passing")
sys.path.insert(0, str(API))

if "dotenv" not in sys.modules:
    stub = types.ModuleType("dotenv")
    stub.load_dotenv = lambda *a, **k: None          # type: ignore[attr-defined]
    sys.modules["dotenv"] = stub

try:
    import main
except Exception as exc:                              # noqa: BLE001
    import traceback
    traceback.print_exc()
    print(f"\nFAIL: `uvicorn main:app` would not start -- {type(exc).__name__}: {exc}")
    raise SystemExit(1)

routes = [r.path for r in main.app.routes if hasattr(r, "path")]
print(f"OK: main imports, {len(routes)} routes registered")

# Second guard, same spirit: every universe ticker that has no explicit TradingView
# symbol must have one in api/tv_symbols.json (or be recorded as unplaceable). A
# ticker added to the universe without one used to fall through to a guessed
# "AMEX:" and fail silently inside TradingView.
import subprocess  # noqa: E402

_r = subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name("build_tv_symbols.py")), "--check"],
                    capture_output=True, text=True)
_out = [l for l in _r.stdout.splitlines() if l.startswith(("OK", "FAIL"))]
print(_out[-1] if _out else (_r.stdout + _r.stderr)[-400:])
if _r.returncode != 0:
    raise SystemExit(1)

# Third guard: the feed-integrity DETECTOR must still detect. It is the thing that is
# supposed to notice a silently starved series, so a bug in it would look exactly like
# a healthy system. One of each failure must be caught, and a clean registry must pass.
import datetime as _dt  # noqa: E402
import freshness as _fr  # noqa: E402

_today = _dt.date(2026, 10, 7)                       # a Wednesday
_reg = [
    {"source": "tradingview", "symbol": "ORPHAN1", "source_symbol": "ORPHAN1"},   # not on the worklist
    {"source": "tradingview", "symbol": "LISTED", "source_symbol": "LISTED"},     # is on the worklist
    {"source": "marketstack", "symbol": "DUP_A", "source_symbol": "XYZ"},         # collision pair
    {"source": "marketstack", "symbol": "DUP_B", "source_symbol": "XYZ"},
    {"source": "marketstack", "symbol": "OK", "source_symbol": "OK"},
]
_last = {"OK": {"date": "2026-10-06", "source": "marketstack"},
         "OLD": {"date": "2026-09-01", "source": "marketstack"},                   # stalled
         "FXLAG": {"date": "2026-09-30", "source": "fred"},                        # 7d old but FRED: fine
         "NONE": None}                                                             # never loaded
_r = _fr.integrity_problems(_reg, {"LISTED"}, ["OK", "OLD", "FXLAG", "NONE"], _last, _today)
_want = (_r["orphans"] == ["ORPHAN1"]
         and [c["symbols"] for c in _r["collisions"]] == [["DUP_A", "DUP_B"]]
         and sorted(s["symbol"] for s in _r["stalled"]) == ["NONE", "OLD"])
_clean = _fr.integrity_problems([_reg[1], _reg[4]], {"LISTED"}, ["OK", "FXLAG"], _last, _today)
if not _want or _clean["n_problems"] != 0:
    print(f"FAIL: feed-integrity detector is wrong: {_r} / clean={_clean}")
    raise SystemExit(1)
print("OK: feed-integrity detector catches an orphan, a collision and stalled tickers, and passes a clean registry")

# Fourth guard: a copy that is ONE date behind FRED is within the nightly-run grace and
# is not a problem; two dates behind has missed a run and is. (DFEDTARU, 2026-10-04.)
if (_fr.is_behind("2026-10-03", "2026-10-04") or not _fr.is_behind("2026-10-02", "2026-10-04")
        or _fr.is_behind("2026-10-04", "2026-10-04") or _fr.is_behind("2026-10-05", "2026-10-04")):
    print("FAIL: freshness.is_behind grace window is wrong")
    raise SystemExit(1)
print("OK: a copy one night behind FRED is not flagged; two nights behind is")

# Fifth guard: the earning-it picker must skip OTC names and names it cannot place, and still
# return n real ones by walking down the ranking (the user does not trade OTC: FGRS, 2026-10-04).
import watchlists as _wl  # noqa: E402

_ex = {"MU": "NASDAQ", "BE": "NYSE", "FGRS": "OTC", "AVGO": "NASDAQ"}
_c = [{"symbol": s} for s in ("FGRS", "MU", "NOSUCH", "BE", "AVGO")]
_picked, _unres, _otc = _wl.pick_earning(_c, _ex, 2)
if [x["symbol"] for x in _picked] != ["MU", "BE"] or _otc != ["FGRS"] or _unres != ["NOSUCH"]:
    print(f"FAIL: pick_earning wrong: {_picked} {_unres} {_otc}")
    raise SystemExit(1)
print("OK: earning-it picker skips OTC and unplaceable names and still fills from the ranking")


# Fourth guard: the pipeline-lag detector. Replays Oct 2026: prices current to 2026-10-02 while the workbook
# still showed 2026-09-30. Must flag the workbook, must stay quiet when the two agree, and must flag a price
# table that has stopped advancing.
_t = __import__("datetime").date(2026, 10, 6)
_frozen = _fr.pipeline_problems({"SPY": "2026-10-02", "QQQ": "2026-10-02", "DBA": "2026-10-02"},
                                {"SPY": "2026-09-30", "QQQ": "2026-09-30", "DBA": "2026-09-30"}, _t)
_ok = _fr.pipeline_problems({"SPY": "2026-10-02", "QQQ": "2026-10-02", "DBA": "2026-10-02"},
                            {"SPY": "2026-10-02", "QQQ": "2026-10-02", "DBA": "2026-10-02"}, _t)
_dead = _fr.pipeline_problems({"SPY": "2026-09-28", "QQQ": "2026-10-05", "DBA": "2026-10-05"},
                              {"SPY": "2026-09-28", "QQQ": "2026-10-05", "DBA": "2026-10-05"}, _t)
if not ({p["check"] for p in _frozen["problems"]} == {"workbook_behind_prices"} and _frozen["n_problems"] == 3
        and _ok["n_problems"] == 0
        and [(p["check"], p["symbol"]) for p in _dead["problems"]] == [("equity_close_behind", "SPY")]):
    print(f"FAIL: pipeline-lag detector is wrong: frozen={_frozen} ok={_ok} dead={_dead}")
    sys.exit(1)
print("OK: pipeline-lag detector flags a workbook behind prices and a stalled close, and passes an in-step pipeline")


# Fifth guard: the referee. Replays Oct 2026: RUT stored to Oct 2 while TradingView had Oct 5 and Oct 6, and a
# futures close stored two hours into the next session (90.79 vs a 91.11 settlement). Must flag both, and pass
# agreeing feeds, a futures bar still in progress, and the 10y's few-bp Treasury-vs-traded gap.
_t = __import__("datetime").date(2026, 10, 7)
_tv = {"RUT": [["2026-10-02", 2832.89], ["2026-10-05", 2847.14], ["2026-10-06", 2830.30]],
       "USOIL": [["2026-10-02", 91.11], ["2026-10-05", 89.43], ["2026-10-06", 89.44], ["2026-10-07", 90.15]],
       "SPX": [["2026-10-05", 7773.95], ["2026-10-06", 7818.93]],
       "US10Y": [["2026-10-06", 5.21]]}
_ours = {"RUT": [("2026-10-01", 2806.63), ("2026-10-02", 2832.90)],
         "USOIL": [("2026-10-02", 90.79), ("2026-10-04", 90.79), ("2026-10-05", 89.43)],
         "SPX": [("2026-10-05", 7773.95), ("2026-10-06", 7818.93)],
         "US10Y": [("2026-10-06", 5.27)]}
_r = _fr.referee_problems(_tv, _ours, _t)
_got = sorted((p["check"], p["symbol"]) for p in _r["problems"])
if _got != [("referee_behind", "RUT"), ("referee_mismatch", "USOIL"), ("referee_weekend", "USOIL")]:
    print(f"FAIL: referee is wrong: {_r}")
    sys.exit(1)
print("OK: referee flags a stalled series and a wrong close, a Sunday-dated row, and passes agreement, in-progress futures and the 10y basis gap")
