"""
cgi_state.py -- tiny keyed JSON store for "what did this look like last time".

Most of CGI's change detection is stateless: themes carry an onset date,
breadth carries its last cross, the Markov layer carries event dates. Two
things are not, and both need memory to avoid reporting a CONDITION as an
EVENT:

  COT extremes   positioning sits pinned at an extreme for months --
                 cot_data's own note records 2011 staying max short while
                 price kept falling. Reporting "at an extreme" every morning
                 would have pushed seven notifications on the first day this
                 ran, all of them the same ag and rates contracts as
                 yesterday. What matters is ENTERING the band.

  fundamentals   a filing does not announce that it differs from the last
                 one (that store is fundamentals_history.py, kept separate
                 because it holds a real per-symbol series rather than a
                 single snapshot).

Deliberately dumb: one small JSON object per key under State/, no TTL, no
versioning. A missing or unreadable blob means "no prior state", and the
caller must treat that as "nothing changed" rather than "everything changed"
-- otherwise the first run after any outage would fire every alert at once.
"""
from __future__ import annotations

import json
import logging

import boto3
from botocore.exceptions import ClientError

REGION = "ap-southeast-1"
BUCKET = "cmon-stage-backend-369568916817-ap-southeast-1-reports"
PREFIX = "State/"

_logger = logging.getLogger("cgi_api.cgi_state")
_s3 = boto3.client("s3", region_name=REGION)


def get(key: str) -> dict:
    try:
        obj = _s3.get_object(Bucket=BUCKET, Key=f"{PREFIX}{key}.json")
        return json.loads(obj["Body"].read().decode("utf-8"))
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return {}
        _logger.warning("[state] get %s failed: %s", key, exc)
        return {}
    except json.JSONDecodeError:
        _logger.error("[state] %s is not valid JSON; treating as empty", key)
        return {}


def put(key: str, value: dict) -> None:
    try:
        _s3.put_object(Bucket=BUCKET, Key=f"{PREFIX}{key}.json",
                       Body=json.dumps(value, allow_nan=False).encode("utf-8"),
                       ContentType="application/json")
    except Exception:
        _logger.exception("[state] put %s failed", key)
