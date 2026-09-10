import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

import backtest_data
import dashboard_data
import macro_data

load_dotenv()

API_TOKEN = os.environ.get("API_TOKEN")

app = FastAPI(title="CGI API", version="0.1.0")

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
):
    if compass_q not in (1, 2, 3, 4) or grid_q not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="compass_q and grid_q must each be 1-4")
    if lookback not in (None, "all", "10y", "5y"):
        raise HTTPException(status_code=400, detail="lookback must be one of: all, 10y, 5y")
    return backtest_data.build_table_response(compass_q, grid_q, min_occ=min_occ, lookback=lookback)


@app.get("/api/backtest/{compass_q}/{grid_q}/occurrences", dependencies=[Depends(require_bearer_token)])
def backtest_occurrences(compass_q: int, grid_q: int, ticker: str):
    if compass_q not in (1, 2, 3, 4) or grid_q not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="compass_q and grid_q must each be 1-4")
    return backtest_data.build_occurrences_response(ticker, compass_q, grid_q)
