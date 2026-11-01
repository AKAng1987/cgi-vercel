"""Index rebalancing calendar and announced results for the Philippines tab: PSEi, MSCI, FTSE, WisdomTree.

The dates are hand-verified from the providers' own documents (source and read date on each row) and kept here so the page can show what
is coming and freshness can say when the table runs out. Announced results (who was added or removed) arrive three ways: the PSE circular
watcher in the daily job (PSEi and the PSE sector indices), EDGE disclosures that mention an index (the Index chip), and a one-shot task on
each announcement day that posts MSCI / FTSE / WisdomTree changes to POST /api/ph/index_events (validated below).
"""
from __future__ import annotations

import datetime as dt
import json
import re
from typing import Optional

PROVIDERS = ("MSCI", "FTSE", "WISDOMTREE", "PSE")
MSCI_SRC = "MSCI press release 12 Aug 2026 (next eight index review dates), https://www.msci.com/eqb/pressreleases/archive/ir_dates.pdf"
FTSE_SRC = "FTSE GEIS 2026 FAQ (review schedule), lseg.com/content/dam/ftse-russell/en_us/documents/policy-documents/ftse-faq-document-geis-2026.pdf"

# provider, event, announce (ISO or None), effective (ISO or None), status: scheduled | estimated | done, note, source
CALENDAR = [
    ("MSCI", "November 2026 Index Review", "2026-11-11", "2026-12-01", "scheduled", "announced after the close; changes effective at the close of 30 Nov", MSCI_SRC),
    ("MSCI", "February 2027 Index Review", "2027-02-09", "2027-03-01", "scheduled", "", MSCI_SRC),
    ("MSCI", "May 2027 Index Review", "2027-05-10", "2027-05-28", "scheduled", "", MSCI_SRC),
    ("MSCI", "August 2027 Index Review", "2027-08-12", "2027-09-01", "scheduled", "", MSCI_SRC),
    ("MSCI", "November 2027 Index Review", "2027-11-11", "2027-12-01", "scheduled", "", MSCI_SRC),
    ("MSCI", "February 2028 Index Review", "2028-02-10", "2028-03-01", "scheduled", "", MSCI_SRC),
    ("FTSE", "GEIS monitor list (December review)", "2026-11-09", None, "scheduled", "subscribers only; the December review is a quarterly share and free-float update, not a constituent review", FTSE_SRC),
    ("FTSE", "GEIS December 2026 quarterly review: final files", "2026-12-04", "2026-12-21", "scheduled", "effective at the open of 21 Dec (after the close of 18 Dec)", FTSE_SRC),
    ("FTSE", "GEIS March 2027 semi-annual review", None, None, "estimated", "constituent changes; FTSE has not published the 2027 dates yet (March 2026 was announced 20 Feb, effective 23 Mar)", FTSE_SRC),
    ("WISDOMTREE", "Emerging-markets annual reconstitution", "2026-10-27", "2026-10-27", "done", "2026 round done; next annual round October 2027 (dates are in WisdomTree's methodology each spring). Philippine changes are not announced per country", "https://www.wisdomtree.com/us/media/core-equity-index-methodology"),
    ("PSE", "PSE indices review: results", "2027-01-27", "2027-02-01", "estimated", "estimated from 2026 (announced 27 Jan, effective 2 Feb); PSE says its new liquidity-weighted method applies from the February 2027 rebalancing; date not yet published", "https://documents.pse.com.ph/CircularOPSPDF/CN-2026-0035.pdf"),
    ("PSE", "PSE indices review: results", "2026-07-27", "2026-08-03", "done", "MYNLD in, CNVRG out of the PSEi (CN-2026-0035)", "https://documents.pse.com.ph/CircularOPSPDF/CN-2026-0035.pdf"),
]
HORIZON_DAYS = 120          # every provider (except one already done) needs a dated event inside this window, or freshness says the table ran out


def calendar_view(today: dt.date, events: Optional[list] = None) -> list[dict]:
    """The calendar with days to go, nearest upcoming first, then the done ones."""
    out = []
    for prov, name, ann, eff, status, note, src in (events or CALENDAR):
        key = ann or eff
        d = dt.date.fromisoformat(key) if key else None
        out.append({"provider": prov, "event": name, "announce": ann, "effective": eff, "status": status, "note": note, "source": src,
                    "days_to_announce": (dt.date.fromisoformat(ann) - today).days if ann else None,
                    "days_to_effective": (dt.date.fromisoformat(eff) - today).days if eff else None})
    up = [e for e in out if e["status"] != "done"]
    up.sort(key=lambda e: (e["announce"] or e["effective"] or "9999"))
    done = sorted((e for e in out if e["status"] == "done"), key=lambda e: e["announce"] or "", reverse=True)
    return up + done


def calendar_problems(today: dt.date, stored_events: list[dict], events: Optional[list] = None) -> dict:
    """Pure freshness check: each provider has an upcoming or estimated event inside HORIZON_DAYS (WisdomTree's yearly round is exempt), and an MSCI
    announcement that passed 2 to 14 days ago has a stored Philippine result (or note)."""
    cal = calendar_view(today, events)
    end = today + dt.timedelta(days=HORIZON_DAYS)
    problems = []
    for prov in ("MSCI", "FTSE", "PSE"):
        have = [e for e in cal if e["provider"] == prov and e["status"] != "done" and (e["announce"] or e["effective"]) and
                today <= dt.date.fromisoformat(e["announce"] or e["effective"]) <= end]
        if not have:
            problems.append({"check": "calendar_" + prov.lower(), "detail": f"no {prov} index event dated in the next {HORIZON_DAYS} days: add the new dates to ph_index.CALENDAR"})
    for e in cal:
        if e["provider"] in ("MSCI",) and e["status"] == "scheduled" and e["announce"] and 2 <= (today - dt.date.fromisoformat(e["announce"])).days <= 14:
            got = [s for s in stored_events if s["provider"] == "MSCI" and abs((dt.date.fromisoformat(s["date"]) - dt.date.fromisoformat(e["announce"])).days) <= 3]
            if not got:
                problems.append({"check": "msci_results", "detail": f"MSCI announced on {e['announce']} but no Philippine result is stored: run the announcement-day task or POST /api/ph/index_events"})
    return {"problems": problems, "n_problems": len(problems)}


# ── announced results: validation of what the announcement-day task posts ─────

MAX_EVENTS = 60
KINDS = ("add", "delete", "note")


def clean_events(body, today: Optional[dt.date] = None) -> tuple[list[dict], dict]:
    """Validate a POST /api/ph/index_events body: {"events": [{provider, date, kind, index, symbols, effective, source_url, note}]}.
    Provider allow-list, PSE tickers only, short text, https source, dates within the last 90 days to 30 ahead. Never raises on a bad row."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    rep = {"received": 0, "kept": 0, "dropped": {}}

    def drop(why):
        rep["dropped"][why] = rep["dropped"].get(why, 0) + 1

    rows = body.get("events") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        return [], {**rep, "error": "body needs events (list)"}
    rows = rows[:MAX_EVENTS]
    rep["received"] = len(rows)
    out = []
    for r in rows:
        if not isinstance(r, dict):
            drop("malformed")
            continue
        prov = str(r.get("provider", "")).upper()
        if prov not in PROVIDERS:
            drop("provider")
            continue
        try:
            d = dt.date.fromisoformat(str(r.get("date"))[:10])
        except ValueError:
            drop("date")
            continue
        if not today - dt.timedelta(days=90) <= d <= today + dt.timedelta(days=30):
            drop("outside window")
            continue
        kind = str(r.get("kind", "note")).lower()
        if kind not in KINDS:
            drop("kind")
            continue
        syms = [str(s).upper() for s in (r.get("symbols") or []) if re.fullmatch(r"[A-Za-z0-9]{1,8}", str(s))][:40]
        if kind in ("add", "delete") and not syms:
            drop("no symbols")
            continue
        url = str(r.get("source_url") or "")
        if url and not re.fullmatch(r"https://[^\s\"'<>]{4,190}", url):
            url = ""
        eff = None
        try:
            eff = dt.date.fromisoformat(str(r.get("effective"))[:10]).isoformat() if r.get("effective") else None
        except ValueError:
            eff = None
        out.append({"provider": prov, "date": d.isoformat(), "kind": kind, "index": str(r.get("index") or "")[:60], "symbols": syms,
                    "effective": eff, "source_url": url, "note": str(r.get("note") or "")[:140]})
    rep["kept"] = len(out)
    return out, rep


def merge_events(old: list[dict], new: list[dict]) -> list[dict]:
    """New rows replace old ones with the same (provider, date, kind, index); the list keeps the newest 200."""
    by = {(e["provider"], e["date"], e["kind"], e["index"]): e for e in old}
    by.update({(e["provider"], e["date"], e["kind"], e["index"]): e for e in new})
    return sorted(by.values(), key=lambda e: e["date"], reverse=True)[:200]


# ── PSE circular: results of the review of PSE indices ────────────────────────

_INDEX_ROWS = ("PSEi", "PSE DivY", "PSE MidCap", "Financials", "Industrial", "Holding Firms", "Property", "Services", "Mining & Oil")


def parse_pse_review(text: str) -> Optional[dict]:
    """Text of a PSE circular. Returns None unless it is the results of an index review. The PSEi change is computed exactly as the difference
    between the listed members and the previous list (a two-column text table cannot be split reliably otherwise); the summary lines of every
    index are kept as written."""
    t = re.sub(r"[ \t]+", " ", text or "")
    if not re.search(r"RESULTS OF THE REVIEW OF PSE INDICES", t, re.I):
        return None
    date = re.search(r"DATE\s*:\s*([A-Za-z]+ \d{1,2}, \d{4})", t)
    eff = re.search(r"effected on ([A-Za-z]+ \d{1,2}, \d{4})", t)
    cn = re.search(r"CN\s*-\s*No\.\s*(\d{4}-\d{4})", t)

    def iso(s):
        try:
            return dt.datetime.strptime(s, "%B %d, %Y").date().isoformat() if s else None
        except ValueError:
            return None
    summary = []
    block = re.search(r"Companies Added Companies Removed(.*?)(?:Attached is a list|All changes)", t, re.S)
    if block:
        for ln in block.group(1).splitlines():
            ln = ln.strip()
            if ln and any(ln.startswith(n) for n in _INDEX_ROWS):
                summary.append(ln[:120])
    members = []
    m = re.search(r"\bPSEi\s*\n\s*Company\s+Stock\s*\n?\s*Code(.*?)(?:PSE DivY|PSE Dividend|\Z)", t, re.S)
    if m:
        members = re.findall(r"^\s*\d{1,2}\s+.+?\s+([A-Z0-9]{2,8})\s*$", m.group(1), re.M)
    return {"circular": cn.group(1) if cn else None, "date": iso(date.group(1)) if date else None, "effective": iso(eff.group(1)) if eff else None,
            "summary": summary, "psei_members": members}


def psei_change(old: list[str], new: list[str]) -> dict:
    return {"added": sorted(set(new) - set(old)), "removed": sorted(set(old) - set(new))}
