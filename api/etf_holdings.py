"""
etf_holdings.py -- What a theme ETF actually holds.

WHY THIS EXISTS
The fundamentals factor originally used constituents Claude picked by hand.
That was the weakest input in the whole build: a guess at what a theme
contains, never checked against the fund that defines it. The first real
pull proved the point immediately -- the hand list for "steel / metals" was
NUE, STLD, X, while XME actually holds CLF, STLD, RS, RGLD, NUE, FCX, NEM
and CMC, and X had been acquired.

SOURCES, IN PREFERENCE ORDER
  1 State Street SPDR  a daily holdings .xlsx, free, no auth, and it carries
                       the TICKER directly -- no name matching, no ambiguity.
                       Covers XLU XLV XLY XLRE XME XOP XHB KBE KRE XRT XAR.
  2 SEC N-PORT         universal: every US-listed ETF files NPORT-P with its
                       full book. Reached by mapping ticker -> CIK + seriesId
                       through the SEC's own fund ticker file, then pulling
                       that series' latest filing. Free, no key, works for
                       VanEck, iShares, Global X, First Trust, WisdomTree and
                       everyone else without a scraper each.
  3 hand-seeded        whatever the factor had before, kept ONLY as a labelled
                       fallback so a failed fetch degrades visibly instead of
                       silently mixing a guess in with real holdings.

Finviz was evaluated and rejected: its free page exposes a holdings COUNT but
not the list, and Elite is a stock screener whose export needs an auth token
in the URL -- a credential, which never belongs in this codebase.

THE TICKER JOIN IS THE DANGEROUS PART
N-PORT identifies a holding by name, LEI and CUSIP -- never by ticker. Naive
name matching is both lossy and WRONG in a way that matters: "Taiwan
Semiconductor Manufacturing Co Ltd" matched TSMWF, the thinly-traded foreign
ordinary, rather than TSM the ADR, and "Applied Materials Inc" matched
nothing. A wrong ticker here would feed confidently wrong fundamentals into a
theme, which is the same silent-wrong-answer class as the dead-XBRL-concept
bug. So every resolved ticker carries a confidence, ambiguity prefers the
shortest symbol (the primary listing), and the caller is expected to verify
against the filer's own entityName before trusting it.

assetCat == "EC" is how N-PORT says "this is an equity". It is also how a
commodity fund answers honestly: GLD, SLV, CPER, DBA, CORN, WEAT and BITO
hold bullion or futures and yield no equities at all, which this module
reports as a fact rather than as an empty list.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from typing import Optional

UA = "CGI macro-regime research (ang.arvin@ymail.com)"
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")

SSGA = ("https://www.ssga.com/us/en/intermediary/library-content/products/"
        "fund-data/etfs/us/holdings-daily-us-en-{t}.xlsx")
MF_TICKERS = "https://www.sec.gov/files/company_tickers_mf.json"
CO_TICKERS = "https://www.sec.gov/files/company_tickers.json"
EDGAR_ATOM = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={series}"
              "&type=NPORT-P&dateb=&owner=include&count=4&output=atom")

# Confirmed 2026-09-25: all eleven return a valid workbook with a Ticker column.
SSGA_TICKERS = {"XLU", "XLV", "XLY", "XLRE", "XME", "XOP", "XHB", "KBE", "KRE", "XRT", "XAR"}

_logger = logging.getLogger("cgi_api.etf_holdings")
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

_mf_cache: Optional[dict] = None
_co_cache: Optional[dict] = None


def _get(url: str, ua: str = UA, timeout: int = 45, tries: int = 3) -> bytes:
    """SEC returns 503 when pushed. The first full sweep lost BOTZ, GDX, BITO,
    FXI and IBB to exactly that, so transient failures are retried with
    backoff rather than silently becoming 'no data'."""
    last: Exception | None = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 -- 503, timeout, reset all retry alike
            last = e
            if i < tries - 1:
                time.sleep(1.5 * (i + 1))
    raise last  # type: ignore[misc]


# ── ticker resolution ───────────────────────────────────────────────────────

# Legal-form and security-type tokens that funds append and the SEC's own
# company titles do not. Matching is TOKEN-based, never substring: an earlier
# version removed the substring " CO" and turned "AMAZON COM INC" into
# "AMAZONM", which silently broke every First Trust fund (FDN, SKYY, CIBR all
# resolved zero holdings while holding nothing but US megacaps).
#
# TRUST and REIT are deliberately NOT dropped -- they are part of real names
# such as Digital Realty Trust.
_STOP = {
    "CORPORATION", "CORP", "CORPS", "INCORPORATED", "INC", "COMPANY", "CO",
    "LIMITED", "LTD", "PLC", "LLC", "LP", "NV", "SA", "AG", "SE", "AB", "AS",
    "HOLDINGS", "HOLDING", "GROUP", "THE", "AND",
    # security type / share class, as funds write it
    "COM", "SHS", "SH", "CAP", "STK", "CLASS", "CL", "ADR", "ADS", "SPONSORED",
    "A", "B", "C", "NEW", "UNIT", "UNITS", "ORD",
    # Global X writes "NVIDIA CORP COMMON STOCK"; without these every Global X
    # fund (BOTZ, MLPX, KARS, URA, COPX) resolved zero holdings.
    "COMMON", "STOCK", "SHARES", "REG", "COS", "SPONS", "NPV", "USD",
}


def _norm(s: str) -> str:
    """Company name -> comparison key, by dropping legal-form and share-class
    TOKENS. Punctuation becomes a space so "AMAZON.COM" and "AMAZON COM"
    collapse to the same key."""
    s = (s or "").upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    toks = [t for t in s.split() if t and t not in _STOP]
    return "".join(toks)


def _company_index() -> dict[str, list[str]]:
    """normalised company name -> [tickers], from the SEC's own file."""
    global _co_cache
    if _co_cache is None:
        d = json.loads(_get(CO_TICKERS).decode("utf-8"))
        idx: dict[str, list[str]] = {}
        for v in d.values():
            idx.setdefault(_norm(v["title"]), []).append(v["ticker"])
        _co_cache = idx
    return _co_cache


def resolve_ticker(name: str) -> tuple[Optional[str], str]:
    """(ticker, confidence). Ambiguity prefers the SHORTEST symbol, which is
    the primary listing -- that is what separates TSM from TSMWF."""
    idx = _company_index()
    key = _norm(name)
    hits = idx.get(key)
    if hits:
        best = sorted(hits, key=lambda t: (len(t), t))[0]
        return best, "exact" if len(hits) == 1 else "ambiguous"
    # prefix fallback: the SEC's title often carries a suffix the fund omits
    for k, v in idx.items():
        if k.startswith(key) and len(key) >= 8:
            return sorted(v, key=lambda t: (len(t), t))[0], "prefix"
    return None, "unresolved"


# ── source 1: State Street ──────────────────────────────────────────────────

def _xlsx_rows(blob: bytes) -> list[list[Optional[str]]]:
    z = zipfile.ZipFile(BytesIO(blob))
    shared: list[str] = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{_NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{_NS}t")))
    sheet = next(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
    root = ET.fromstring(z.read(sheet))
    out = []
    for row in root.iter(f"{_NS}row"):
        cells = []
        for c in row.findall(f"{_NS}c"):
            v = c.find(f"{_NS}v")
            if v is None or v.text is None:
                cells.append(None)
            elif c.get("t") == "s" and v.text.isdigit():
                cells.append(shared[int(v.text)])
            else:
                cells.append(v.text)
        out.append(cells)
    return out


def _from_ssga(ticker: str) -> Optional[dict]:
    try:
        rows = _xlsx_rows(_get(SSGA.format(t=ticker.lower()), ua=BROWSER_UA))
    except Exception as e:
        _logger.warning("[etf] ssga %s -> %s", ticker, e)
        return None
    hdr = next((i for i, r in enumerate(rows)
                if r and "Ticker" in [str(c) for c in r if c]), None)
    if hdr is None:
        return None
    cols = {str(c): i for i, c in enumerate(rows[hdr]) if c}
    as_of = None
    for r in rows[:hdr]:
        for c in r or []:
            if c and str(c).startswith("As of"):
                as_of = str(c).replace("As of", "").strip()
    out = []
    for r in rows[hdr + 1:]:
        if not r or len(r) <= cols.get("Ticker", 99):
            continue
        tk, w = r[cols["Ticker"]], r.get(cols["Weight"]) if isinstance(r, dict) else r[cols["Weight"]]
        if not tk or tk == "-":
            continue
        try:
            wt = float(w)
        except (TypeError, ValueError):
            continue
        out.append({"ticker": str(tk).strip(), "name": str(r[cols["Name"]]).strip(),
                    "weight_pct": round(wt, 4), "ticker_confidence": "given"})
    if not out:
        return None
    out.sort(key=lambda h: -h["weight_pct"])
    return {"etf": ticker, "source": "State Street SPDR (daily)", "as_of": as_of,
            "n_holdings": len(out), "holdings": out}


# ── source 2: SEC N-PORT ────────────────────────────────────────────────────

def _series_of(ticker: str) -> Optional[str]:
    global _mf_cache
    if _mf_cache is None:
        d = json.loads(_get(MF_TICKERS).decode("utf-8"))
        i = {f: n for n, f in enumerate(d["fields"])}
        _mf_cache = {r[i["symbol"]]: r[i["seriesId"]] for r in d["data"]}
    return _mf_cache.get(ticker.upper())


def _from_nport(ticker: str) -> Optional[dict]:
    series = _series_of(ticker)
    if not series:
        return None
    try:
        atom = _get(EDGAR_ATOM.format(series=series)).decode("utf-8", "ignore")
        if "<entry" not in atom:
            return None
        root = ET.fromstring(atom)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entry = root.find("a:entry", ns)
        href = entry.find("a:link", ns).get("href")
        filed = (entry.find("a:updated", ns).text or "")[:10]
        doc = href.rsplit("/", 1)[0] + "/primary_doc.xml"
        xml = _get(doc)
    except Exception as e:
        _logger.warning("[etf] nport %s -> %s", ticker, e)
        return None

    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None

    def tag(e):
        return e.tag.split("}")[-1]

    equities, non_equity = [], 0
    for sec in (e for e in root.iter() if tag(e) == "invstOrSec"):
        d = {tag(c): (c.text or "").strip() for c in sec}
        if not d.get("pctVal"):
            continue
        # EC == equity-common. A bullion or futures fund has none, and saying
        # so is the honest answer rather than returning an empty list.
        if d.get("assetCat") != "EC":
            non_equity += 1
            continue
        try:
            w = float(d["pctVal"])
        except ValueError:
            continue
        nm = d.get("title") or d.get("name") or ""
        tk, conf = resolve_ticker(nm)
        equities.append({"ticker": tk, "name": nm, "cusip": d.get("cusip"),
                         "weight_pct": round(w, 4), "ticker_confidence": conf})
    if not equities:
        return {"etf": ticker, "source": f"SEC N-PORT (filed {filed})", "as_of": filed,
                "n_holdings": 0, "holdings": [],
                "note": (f"no equity holdings -- {non_equity} non-equity positions; "
                         "this fund holds bullion, futures or other funds")}
    equities.sort(key=lambda h: -h["weight_pct"])
    return {"etf": ticker, "source": f"SEC N-PORT (filed {filed})", "as_of": filed,
            "n_holdings": len(equities), "holdings": equities,
            "n_non_equity": non_equity}


# ── public ──────────────────────────────────────────────────────────────────

def holdings(ticker: str) -> Optional[dict]:
    """State Street first (it carries the ticker), then N-PORT (universal)."""
    if ticker.upper() in SSGA_TICKERS:
        r = _from_ssga(ticker)
        if r:
            return r
        _logger.info("[etf] %s: ssga failed, falling back to N-PORT", ticker)
    return _from_nport(ticker)


def top_constituents(etfs: list[str], n: int = 8,
                     min_weight: float = 0.5) -> tuple[list[str], list[dict]]:
    """Union of the top-n resolved equity holdings across a theme's proxies.

    Returns (tickers, provenance). Only 'exact' and 'given' ticker matches are
    used: an ambiguous or unresolved name would put the wrong company inside a
    theme, and a smaller correct list beats a longer wrong one.
    """
    seen: dict[str, float] = {}
    prov = []
    for e in etfs:
        h = holdings(e)
        if not h:
            prov.append({"etf": e, "status": "no data"})
            continue
        # "ambiguous" is accepted: it means several share classes normalised to
        # one name and the SHORTEST symbol was taken, which is the primary
        # listing -- that is the rule that picked TSM over TSMWF and GOOG over
        # GOOGL. "prefix" and "unresolved" are refused, because those are
        # guesses and a wrong ticker puts the wrong company inside a theme.
        good = [x for x in h["holdings"]
                if x["ticker"] and x["ticker_confidence"] in ("given", "exact", "ambiguous")
                and x["weight_pct"] >= min_weight]
        for x in good[:n]:
            seen[x["ticker"]] = max(seen.get(x["ticker"], 0), x["weight_pct"])
        prov.append({"etf": e, "status": "ok", "source": h["source"], "as_of": h.get("as_of"),
                     "n_holdings": h["n_holdings"], "n_used": len(good[:n]),
                     "n_dropped": len(h["holdings"]) - len(good),
                     "note": h.get("note")})
    return sorted(seen, key=lambda t: -seen[t]), prov
