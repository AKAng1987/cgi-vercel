"""
policy_watch.py -- Candidate policy events from central bank feeds.

The point of the POLICY register is to be early: a policy lands, it names
the themes to watch, and those get checked against relative strength. That
only works if the announcement reaches CGI when it happens rather than six
months after the rally.

This module does the watching half. It reads central banks' own public RSS
feeds -- free, no key, no scraping around a block -- filters for items that
look like policy rather than routine statistics, and returns them as
CANDIDATES. Nothing is promoted automatically: a candidate becomes a POLICY
note only when the user confirms it, because deciding that an announcement
matters is judgement, not pattern matching.

Coverage is what publishes a usable feed. The Fed, ECB, BOJ and BoE do.
Bank Indonesia and BSP block automated requests (403); the PBoC and Bank of
Korea publish HTML without a feed. Those stay manual, and the module says so
rather than quietly omitting them.

FMP's news and economics endpoints would have covered more, but both are
gated to the Starter plan and the user is on free.
"""
from __future__ import annotations

import datetime as dt
import html
import re
import urllib.request

FEEDS: list[tuple[str, str, str]] = [
    ("US", "Federal Reserve", "https://www.federalreserve.gov/feeds/press_monetary.xml"),
    ("EU", "ECB", "https://www.ecb.europa.eu/rss/press.html"),
    ("JP", "Bank of Japan", "https://www.boj.or.jp/en/rss/whatsnew.xml"),
    ("GB", "Bank of England", "https://www.bankofengland.co.uk/rss/news"),
]

# Sources with no usable feed -- recorded so the gap is visible on the page
# instead of looking like "nothing happened there".
NO_FEED = [
    ("PH", "Bangko Sentral ng Pilipinas", "blocks automated requests (403)"),
    ("KR", "Bank of Korea", "HTML only, no RSS"),
    ("CN", "People's Bank of China", "HTML only, no RSS"),
]

# Policy-shaped language. Deliberately broad: a missed candidate is worse
# than an extra one the user waves away in two seconds.
KEYWORDS = {
    "monetary": ["rate decision", "interest rate", "monetary policy", "fomc", "policy rate",
                 "bank rate", "asset purchase", "quantitative", "tightening", "easing",
                 "statement", "projections", "yield curve control", "facility", "repo"],
    "fiscal": ["budget", "fiscal", "spending", "stimulus", "package", "subsidy", "tax"],
    "trade": ["tariff", "trade", "export control", "sanction", "quota"],
}
# Routine statistical publications that are not policy
NOISE = ["statistics on", "statistical", "release of", "survey results", "monthly report on",
         "flow of funds", "balance of payments", "money stock", "loans and discounts"]


def _classify(title: str) -> str | None:
    t = title.lower()
    if any(n in t for n in NOISE):
        return None
    for kind, words in KEYWORDS.items():
        if any(w in t for w in words):
            return kind
    return None


def _parse(xml: str) -> list[tuple[str, str, str]]:
    out = []
    for block in re.findall(r"<item[^>]*>(.*?)</item>", xml, re.S):
        t = re.search(r"<title[^>]*>(.*?)</title>", block, re.S)
        d = re.search(r"<(?:pubDate|dc:date)[^>]*>(.*?)</", block, re.S)
        l = re.search(r"<link[^>]*>(.*?)</link>", block, re.S)
        if not t:
            continue
        title = html.unescape(re.sub(r"<!\[CDATA\[|\]\]>|<[^>]+>", "", t.group(1))).strip()
        raw = html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", d.group(1))).strip() if d else ""
        link = html.unescape(re.sub(r"<!\[CDATA\[|\]\]>|<[^>]+>", "", l.group(1))).strip() if l else ""
        out.append((title, raw, link))
    return out


def _date(raw: str) -> str | None:
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                "%a, %d %b %Y", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(raw.strip()[:len(dt.datetime.now().strftime(fmt)) + 8].strip(), fmt).date().isoformat()
        except Exception:
            continue
    m = re.search(r"(\d{1,2})\s+(\w{3})\s+(\d{4})", raw)
    if m:
        try:
            return dt.datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y").date().isoformat()
        except Exception:
            pass
    m = re.search(r"(\d{4}-\d{2}-\d{2})", raw)
    return m.group(1) if m else None


def build_policy_watch(days: int = 45) -> dict:
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    candidates, errors = [], []
    for country, source, url in FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (CGI policy watch)"})
            xml = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
        except Exception as e:
            errors.append({"country": country, "source": source, "error": str(e)[:120]})
            continue
        for title, raw, link in _parse(xml):
            kind = _classify(title)
            if not kind:
                continue
            d = _date(raw)
            if d and d < cutoff:
                continue
            candidates.append({"country": country, "source": source, "type": kind,
                               "announced": d, "title": title, "link": link})
    candidates.sort(key=lambda c: (c["announced"] or "", c["country"]), reverse=True)
    return {
        "as_of": dt.date.today().isoformat(),
        "window_days": days,
        "candidates": candidates,
        "no_feed": [{"country": c, "source": s, "reason": r} for c, s, r in NO_FEED],
        "errors": errors,
        "note": ("Candidates only. A candidate becomes a POLICY note when you confirm it -- "
                 "deciding an announcement matters is judgement, not pattern matching. "
                 "Filters are deliberately broad: an extra candidate costs two seconds, a "
                 "missed one costs the trade."),
    }
