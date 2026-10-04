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
