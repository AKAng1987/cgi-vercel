"""
customer_links.py -- who pays whom, from the filings rather than from memory.

THE POINT
The LINKS map in fundamentals_data is hand-written and therefore only as good
as whoever wrote it. The one HARD fact in this area is the SEC requirement to
disclose any customer above 10% of revenue, and that disclosure is machine-
readable from the 10-K itself. This turns guesses into sourced facts.

WHAT IT CAN AND CANNOT GIVE YOU -- read this before trusting the output.
The disclosure reliably gives the PERCENTAGE. It gives the NAME only
sometimes. NVDA's 2026 10-K is the canonical example: "sales to one direct
customer represented 22% of total revenue and sales to another direct customer
represented 14%" -- two enormous relationships, neither counterparty named.

So this produces two different things, and they are kept apart:
  concentration  "this company has a 22% customer"  -- almost always available
  named link     "this company's 22% customer is X" -- only when disclosed

Concentration alone is still worth having: it says where the revenue is
fragile without saying to whom.

CANDIDATES, NOT LINKS
Nothing is promoted automatically, exactly as policy_watch does with central
bank announcements. A parsed sentence becomes a link in the map only when a
human confirms it. Auto-promoting a regex match into a map used to read one
company's results through to another is the same silent-wrong-answer class as
the dead-XBRL-concept bug -- it would be confidently wrong and invisible.

COST
A 10-K is 2-10MB. This is why the universe is a parameter rather than the full
134 names, and why the result is cached for a week: the filings only change
once a year.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import logging
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import sec_xbrl as sx

SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"

# Sentences that disclose a customer above the reporting threshold. Two
# patterns because filers phrase it both ways, and both are kept verbatim so a
# human can judge the match rather than trust the regex.
PATTERNS = [
    re.compile(r"[^.]{0,400}?[Cc]ustomer[^.]{0,400}?(?:accounted for|represented|comprised)"
               r"[^.]{0,200}?\d{1,3}(?:\.\d)?%[^.]{0,300}\.", re.S),
    re.compile(r"[^.]{0,400}?(?:accounted for|represented)[^.]{0,120}?\d{1,3}(?:\.\d)?%"
               r"[^.]{0,200}?(?:of (?:our |total |net )?(?:revenue|sales))[^.]{0,200}\.", re.S),
]
PCT = re.compile(r"(\d{1,3}(?:\.\d)?)%")

# GEOGRAPHIC disclosures use the same words and the same percentages but mean
# something else entirely -- NVDA's top match was "customers headquartered
# outside of the United States accounted for 41% of revenue", which is a
# revenue-by-region fact, not a counterparty. Excluded outright.
GEOGRAPHIC = re.compile(r"\b(?:country|countries|headquarter|geograph|region|"
                        r"outside of the United States|United States and)\b", re.I)

# NEGATIVE disclosures -- "no customer accounted for 10% or more" -- are worth
# keeping, because "this company has no concentration" is a real finding, but
# they are the opposite of a link and must never be presented as one.
NEGATIVE = re.compile(r"\bno\s+(?:single\s+|individual\s+|one\s+)?customer", re.I)

# A counterparty is "named" only on at least two capitalised words before the
# suffix, and never when the phrase is the filer talking about itself. An
# earlier, looser version matched "Com" out of "the Company" and invented a
# counterparty for TWLO -- a fabricated name is far worse than no name.
NAMED = re.compile(r"\b((?:[A-Z][A-Za-z&.\-]{2,} ){1,3}"
                   r"(?:Inc|Corp|Corporation|Ltd|Limited|LLC|PLC|AG|SA|NV|Technologies|Systems)\b)")
SELF_REF = re.compile(r"\b(?:the|our|its)\s+Compan(?:y|ies)\b", re.I)

_logger = logging.getLogger("cgi_api.customer_links")


def _get(url: str, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": sx.UA,
                                              "Accept-Encoding": "gzip, deflate"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return gzip.decompress(raw) if r.headers.get("Content-Encoding") == "gzip" else raw


def _latest_10k(cik: int) -> tuple[Optional[str], Optional[str]]:
    try:
        d = json.loads(_get(SUBMISSIONS.format(cik=cik), timeout=45).decode("utf-8"))
    except Exception:
        return None, None
    rec = d.get("filings", {}).get("recent", {})
    for i, form in enumerate(rec.get("form", [])):
        if form == "10-K":
            acc = rec["accessionNumber"][i].replace("-", "")
            return ARCHIVE.format(cik=cik, acc=acc, doc=rec["primaryDocument"][i]), rec["filingDate"][i]
    return None, None


def _sentences(html: str) -> list[str]:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&#?\w{1,8};", " ", text)
    text = re.sub(r"\s+", " ", text)
    seen, out = set(), []
    for pat in PATTERNS:
        for m in pat.findall(text):
            sm = m.strip()
            key = sm[:80].lower()
            if 60 < len(sm) < 600 and key not in seen:
                seen.add(key)
                out.append(sm)
    return out


def for_symbol(sym: str) -> dict:
    cik = sx.cik_map().get(sym.upper())
    if cik is None:
        return {"symbol": sym, "status": "not an SEC filer"}
    url, filed = _latest_10k(cik)
    if not url:
        return {"symbol": sym, "status": "no 10-K (likely a 20-F/40-F filer)"}
    try:
        html = _get(url).decode("utf-8", "ignore")
    except Exception as exc:
        _logger.warning("[links] %s: %s", sym, exc)
        return {"symbol": sym, "status": f"fetch failed: {type(exc).__name__}"}

    cands = []
    for sent in _sentences(html):
        if GEOGRAPHIC.search(sent):
            continue                       # revenue-by-region, not a counterparty
        pcts = [float(p) for p in PCT.findall(sent)]
        negative = bool(NEGATIVE.search(sent))
        names = [] if (negative or SELF_REF.search(sent)) else [
            n.strip() for n in NAMED.findall(sent)]
        cands.append({
            "quote": sent,
            "max_pct": max(pcts) if pcts else None,
            "named_counterparty": names[0] if names else None,
            "kind": ("no concentration disclosed" if negative
                     else "named link" if names else "concentration only"),
        })
    # Real concentrations first, then negatives -- a "no customer over 10%"
    # is a finding but should never outrank an actual 22% relationship.
    cands.sort(key=lambda c: (c["kind"] == "no concentration disclosed",
                              -(c["max_pct"] or 0)))
    return {"symbol": sym, "status": "ok", "filed": filed, "source": url,
            "candidates": cands[:6],
            "n_named": sum(1 for c in cands if c["named_counterparty"])}


def build_customer_links(symbols: list[str]) -> dict:
    with ThreadPoolExecutor(max_workers=3) as ex:
        rows = list(ex.map(for_symbol, symbols))
    ok = [r for r in rows if r.get("status") == "ok"]
    return {
        "as_of": dt.date.today().isoformat(),
        "source": "SEC 10-K primary documents, parsed for 10%-customer disclosure",
        "n_symbols": len(symbols),
        "n_with_disclosure": sum(1 for r in ok if r.get("candidates")),
        "n_named": sum(r.get("n_named", 0) for r in ok),
        "note": ("Candidates, not links. The disclosure reliably gives the PERCENTAGE and only "
                 "sometimes the NAME -- NVDA discloses a 22% and a 14% customer without naming "
                 "either. Confirm a row before it goes into the map; nothing here is promoted "
                 "automatically, the same rule policy_watch follows."),
        "companies": rows,
    }
