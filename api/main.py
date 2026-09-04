import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

import dashboard_data

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
