import logging
import os
import threading
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

import backtest_data
import cache
import dashboard_data
import macro_data
import markov_data
import series_write
import cot_data
import policy_watch
import notes_data
import fundamentals_data
import brief_data
import technicals_data
import themes_data
import signals_data
import watchlists as watchlists_data

load_dotenv()

API_TOKEN = os.environ.get("API_TOKEN")

_logger = logging.getLogger("cgi_api")

app = FastAPI(title="CGI API", version="0.1.0")


@app.on_event("startup")
def _warm_up_caches() -> None:
    """Post-deploy self-warm: fire the three biggest cache-fed endpoints
    off-thread on boot so the first real visitor doesn't eat the cold-
    start GetObject latency (~1-2s per S3 client init + first fetch).
    Free-tier Render cold-boot alone is ~75s of Python/boto3 import;
    this doesn't fix that, only ensures once we're up we're actually hot.
    All failures swallowed -- a failed pre-warm must not fail startup."""
    def _run() -> None:
        for name, fn in [
            ("macro/rates", macro_data.build_rates_response),
            ("macro/growth", macro_data.build_growth_response),
            ("live", lambda: dashboard_data.build_live_response(date_str=None)),
            ("markov/axis_drivers", lambda: cache.get_or_fetch("axis_drivers", __import__("axis_drivers").compute_axis_drivers)),
            ("watchlists", lambda: cache.get_or_fetch("watchlists", watchlists_data.build_watchlists_response)),
        ]:
            try:
                fn()
                _logger.info("[warm-up] %s primed", name)
            except Exception as exc:  # noqa: BLE001
                _logger.warning("[warm-up] %s failed: %s", name, exc)

    threading.Thread(target=_run, name="cgi-warmup", daemon=True).start()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_bearer_token(request: Request) -> None:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = auth_header.removeprefix("Bearer ").strip()
    if not API_TOKEN or token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/")
def root():
    return {"service": "CGI API", "status": "up"}


@app.get("/api/health", dependencies=[Depends(require_bearer_token)])
def health():
    return {"status": "ok", "service": "CGI API", "version": "0.1.0"}


@app.get("/api/live", dependencies=[Depends(require_bearer_token)])
def live(date: Optional[str] = None):
    try:
        return dashboard_data.build_live_response(date_str=date)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/macro/rates", dependencies=[Depends(require_bearer_token)])
def macro_rates():
    return macro_data.build_rates_response()


@app.get("/api/macro/growth", dependencies=[Depends(require_bearer_token)])
def macro_growth():
    return macro_data.build_growth_response()


@app.get("/api/macro/dot-plot", dependencies=[Depends(require_bearer_token)])
def macro_dot_plot():
    return macro_data.build_dot_plot_response()


@app.get("/api/backtest/{compass_q}/{grid_q}", dependencies=[Depends(require_bearer_token)])
def backtest_table(
    compass_q: int,
    grid_q: int,
    min_occ: int = 5,
    lookback: Optional[str] = None,
    trend: Optional[str] = None,
    from_combo: Optional[str] = None,
):
    if compass_q not in (1, 2, 3, 4) or grid_q not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="compass_q and grid_q must each be 1-4")
    if from_combo not in (None, "all") and not (len(from_combo) == 4 and from_combo[0] == "C" and from_combo[2] == "G"
                                                 and from_combo[1] in "1234" and from_combo[3] in "1234"):
        raise HTTPException(status_code=400, detail="from_combo must look like C2G3 or all")
    if lookback not in (None, "all", "10y", "5y"):
        raise HTTPException(status_code=400, detail="lookback must be one of: all, 10y, 5y")
    if trend not in (None, *backtest_data.TREND_BUCKETS):
        raise HTTPException(status_code=400, detail="trend must be one of: all, extended, neutral, oversold")
    return backtest_data.build_table_response(compass_q, grid_q, min_occ=min_occ, lookback=lookback, trend=trend, from_combo=from_combo)


@app.get("/api/backtest/{compass_q}/{grid_q}/occurrences", dependencies=[Depends(require_bearer_token)])
def backtest_occurrences(compass_q: int, grid_q: int, ticker: str):
    if compass_q not in (1, 2, 3, 4) or grid_q not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="compass_q and grid_q must each be 1-4")
    return backtest_data.build_occurrences_response(ticker, compass_q, grid_q)


@app.get("/api/signals", dependencies=[Depends(require_bearer_token)])
def signals(limit: Optional[int] = None):
    if limit is not None and limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")
    return signals_data.build_signals_response(limit=limit)


@app.get("/api/markov", dependencies=[Depends(require_bearer_token)])
def markov():
    return markov_data.build_markov_response()


@app.get("/api/series")
def series_describe():
    """Public: which manually-loaded series exist and their last stored date."""
    return series_write.describe()


@app.post("/api/series/{symbol}")
def series_append(symbol: str, body: dict):
    """Public but append-only, whitelisted and range-checked -- see series_write.py."""
    return series_write.append(symbol, body.get("rows"))


@app.get("/api/cot", dependencies=[Depends(require_bearer_token)])
def cot():
    return cache.get_or_fetch("cot", cot_data.build_cot_response)


@app.get("/api/policy-watch", dependencies=[Depends(require_bearer_token)])
def policy_watch_endpoint(days: int = 45):
    return cache.get_or_fetch("policy_watch", lambda: policy_watch.build_policy_watch(days))


@app.get("/api/notes", dependencies=[Depends(require_bearer_token)])
def notes():
    """Policy notes are marked live when a theme they point at is still
    running on RS, so this reads the theme detector rather than taking the
    list from the caller."""
    try:
        th = cache.get_or_fetch("themes", themes_data.build_themes_response)
        active = [t["theme"] for t in th.get("themes", []) if t.get("stage")]
    except Exception:
        active = []
    return notes_data.build_notes_response(active_themes=active)


@app.get("/api/technicals", dependencies=[Depends(require_bearer_token)])
def technicals():
    return cache.get_or_fetch("technicals", technicals_data.build_technicals_response)


@app.get("/api/themes", dependencies=[Depends(require_bearer_token)])
def themes():
    return cache.get_or_fetch("themes", themes_data.build_themes_response)


@app.get("/api/fundamentals", dependencies=[Depends(require_bearer_token)])
def fundamentals():
    """Layer 3 of the brief: who inside each theme is capturing the money.

    Live from SEC XBRL -- no key needed, so unlike ISM this does not depend on
    a connector staying up. Themes still running on RS are flagged is_live the
    same way /api/notes does it, so the page can lead with the live ones.
    """
    try:
        th = cache.get_or_fetch("themes", themes_data.build_themes_response)
        active = [t["theme"] for t in th.get("themes", []) if t.get("stage")]
    except Exception:
        active = []
    # Background refresh: the universe is ~116 names derived from real ETF
    # holdings and a cold recompute takes ~30s, which would exceed the Vercel
    # server component's function timeout and fail the page rather than just
    # be slow. Serve the previous value, refresh behind it.
    return cache.get_or_fetch_bg(
        "fundamentals",
        lambda: fundamentals_data.build_fundamentals_response(active_themes=active),
    )


@app.get("/api/brief", dependencies=[Depends(require_bearer_token)])
def brief(cadence: str = "daily"):
    """The morning brief. Manila morning is after the US close, so the daily
    edition covers the session that just finished.

    Importance is not decided here: every headline comes from cgi_changes,
    where each event is a rule that already existed in CGI, ranked by how
    rarely it actually fires. If nothing crossed, it says so.
    """
    key = "brief_weekly" if cadence == "weekly" else "brief_daily"
    return cache.get_or_fetch(key, lambda: brief_data.build_brief(cadence))


@app.get("/api/watchlists")
def watchlists():
    """Public, read-only: ticker lists per regime for the TradingView cloud
    routine. Nothing sensitive, so no bearer -- the routine runs in an
    environment that cannot hold secrets."""
    return cache.get_or_fetch("watchlists", watchlists_data.build_watchlists_response)
