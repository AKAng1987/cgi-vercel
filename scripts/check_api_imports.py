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
