"""
erp_parse.py -- read Damodaran's implied-ERP workbooks. Standard library only, so the API, the loader script and the
research code can all share it.

  ERPbymonth.xlsx  monthly, start-of-month rows since 2008-09     (pages.stern.nyu.edu/~adamodar/pc/implprem/)
  histimpl.xlsx    annual, year-end rows since 1960               (pages.stern.nyu.edu/~adamodar/pc/datasets/)

Columns are found by their HEADER TEXT, not by letter. If Damodaran inserts a column the values stay right; if he
renames one of the two essential columns the parse raises instead of quietly returning the wrong series.

The workbook is untrusted data from the internet: read with zipfile + ElementTree only (no formulas, no macros,
nothing executed), size-limited, and every value range-checked.
"""
from __future__ import annotations

import datetime as dt
import io
import re
import zipfile
import xml.etree.ElementTree as ET

MONTHLY_URL = "https://pages.stern.nyu.edu/~adamodar/pc/implprem/ERPbymonth.xlsx"
ANNUAL_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/histimpl.xlsx"
MAX_BYTES, MAX_UNZIPPED = 5_000_000, 30_000_000
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}

# symbol -> (exact header text, min, max, essential).   Values are converted fraction -> percent.
MONTHLY_COLS = {
    "ERP_T12M":         ("ERP (T12m)", 0.0, 25.0, True),
    "ERP_TBOND":        ("T.Bond Rate", 0.0, 20.0, True),
    "ERP_SUSTAINABLE":  ("ERP (T12 m with sustainable payout)", 0.0, 25.0, False),
    "ERP_ADJ_RF":       ("ERP (T12m) with adj riskfree rate", 0.0, 25.0, False),
    "ERP_NORMALIZED":   ("ERP (Normalized)", 0.0, 25.0, False),
    "ERP_NET_CASH":     ("ERP (Net Cash Yield)", 0.0, 25.0, False),
    "ERP_EXPECTED_RET": ("Expected Return", 0.0, 30.0, False),
    "ERP_GROWTH":       ("Expected growth rate", -10.0, 40.0, False),
}
ANNUAL_COLS = {
    "ERP_ANNUAL":        ("Implied ERP (FCFE)", 0.0, 25.0, True),
    "ERP_ANNUAL_TBOND":  ("T.Bond Rate", 0.0, 20.0, True),
}


def _open(data: bytes) -> zipfile.ZipFile:
    if len(data) > MAX_BYTES:
        raise ValueError("workbook larger than expected; refusing to parse it")
    z = zipfile.ZipFile(io.BytesIO(data))
    if sum(i.file_size for i in z.infolist()) > MAX_UNZIPPED:
        raise ValueError("workbook expands too large; refusing to parse it")
    return z


def _first_sheet(z: zipfile.ZipFile) -> tuple[list[dict], bool]:
    """Rows of the workbook's FIRST sheet as {column letter: raw text}, and whether dates use the 1904 system."""
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    is1904 = (wb.find("m:workbookPr", _NS) is not None
              and wb.find("m:workbookPr", _NS).get("date1904") in ("1", "true"))
    rid = wb.find(".//m:sheet", _NS).get("{%s}id" % _NS["r"])
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = next(r.get("Target") for r in rels if r.get("Id") == rid)
    path = target.lstrip("/") if target.startswith("/") else "xl/" + target
    ss = ["".join(t.itertext()) for t in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS)]
    rows = []
    for r in ET.fromstring(z.read(path)).iter("{%s}row" % _NS["m"]):
        cells = {}
        for c in r.findall("m:c", _NS):
            v = c.find("m:v", _NS)
            if v is not None:
                cells[re.match(r"[A-Z]+", c.get("r")).group(0)] = ss[int(v.text)] if c.get("t") == "s" else v.text
        rows.append(cells)
    return rows, is1904


def _columns(header: dict, spec: dict) -> dict[str, str]:
    by_text = {(v or "").strip(): k for k, v in header.items()}
    cols = {}
    for sym, (text, _lo, _hi, essential) in spec.items():
        col = by_text.get(text)
        if col is None:
            # headers sometimes carry trailing words; accept a unique prefix match
            hits = [k for t, k in by_text.items() if t.startswith(text)]
            col = hits[0] if len(hits) == 1 else None
        if col is None and essential:
            raise ValueError(f"layout changed: column {text!r} not found in the header row")
        if col is not None:
            cols[sym] = col
    return cols


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_monthly(data: bytes) -> dict[str, list[tuple[str, float]]]:
    z = _open(data)
    rows, is1904 = _first_sheet(z)
    if not rows or "Start of month" not in (rows[0].get("A") or ""):
        raise ValueError("unexpected layout: header row did not start with 'Start of month'")
    cols = _columns(rows[0], MONTHLY_COLS)
    base = dt.date(1904, 1, 1) if is1904 else dt.date(1899, 12, 30)
    out: dict[str, list[tuple[str, float]]] = {k: [] for k in cols}
    for c in rows[1:]:
        a = (c.get("A") or "").strip()
        try:
            d = base + dt.timedelta(days=int(float(a)))
        except ValueError:
            try:
                d = dt.datetime.strptime(a, "%d-%b-%y").date()      # some rows hold text dates like 1-Sep-24
            except ValueError:
                continue
        for sym, col in cols.items():
            v = _num(c.get(col))
            _t, lo, hi, _e = MONTHLY_COLS[sym]
            if v is not None and lo <= v * 100.0 <= hi:
                out[sym].append((d.isoformat(), round(v * 100.0, 4)))
    for s in out:
        out[s].sort()
    return out


def parse_annual(data: bytes, today: dt.date | None = None) -> dict[str, list[tuple[str, float]]]:
    z = _open(data)
    rows, _is1904 = _first_sheet(z)
    hdr_i = next((i for i, r in enumerate(rows) if (r.get("A") or "").strip() == "Year"), None)
    if hdr_i is None:
        raise ValueError("unexpected layout: no 'Year' header row")
    cols = _columns(rows[hdr_i], ANNUAL_COLS)
    today = today or dt.date.today()
    out: dict[str, list[tuple[str, float]]] = {k: [] for k in cols}
    for c in rows[hdr_i + 1:]:
        y = _num(c.get("A"))
        if y is None or not (1900 <= int(y) <= 2100):
            continue
        d = dt.date(int(y), 12, 31)                       # his annual figure is the year-end estimate
        if d > today:
            continue
        for sym, col in cols.items():
            v = _num(c.get(col))
            _t, lo, hi, _e = ANNUAL_COLS[sym]
            if v is not None and lo <= v * 100.0 <= hi:
                out[sym].append((d.isoformat(), round(v * 100.0, 4)))
    for s in out:
        out[s].sort()
    return out


# ── country risk premiums (ctryprem.xlsx, sheet "ERPs by country") ────────────────────────────────────────────────
COUNTRY_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xlsx"
COUNTRY_SHEET = "ERPs by country"
# CGI country code -> Damodaran's name. The euro area has no single row (it is a bloc), so it is left out on purpose.
COUNTRY_MAP = {
    "PH": "Philippines", "CN": "China", "JP": "Japan", "KR": "Korea", "GB": "United Kingdom", "IN": "India",
    "ID": "Indonesia", "TW": "Taiwan", "HK": "Hong Kong", "SG": "Singapore", "MY": "Malaysia", "VN": "Vietnam",
    "AU": "Australia", "CA": "Canada", "CH": "Switzerland", "BR": "Brazil", "MX": "Mexico", "ZA": "South Africa",
    "US": "United States",
}
# series prefix -> (exact header text, min, max); fractions are converted to percent
COUNTRY_COLS = {
    "CRP_ERP":    ("Total Equity Risk Premium", 0.0, 40.0),
    "CRP_PREM":   ("Country Risk Premium", 0.0, 40.0),
    "CRP_SPREAD": ("Rating-based Default Spread", 0.0, 40.0),
}


def _sheet_by_name(z: zipfile.ZipFile, name: str) -> list[dict]:
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    sh = next((s for s in wb.iter("{%s}sheet" % _NS["m"]) if (s.get("name") or "").strip() == name), None)
    if sh is None:
        raise ValueError(f"layout changed: sheet {name!r} not found")
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = next(r.get("Target") for r in rels if r.get("Id") == sh.get("{%s}id" % _NS["r"]))
    path = target.lstrip("/") if target.startswith("/") else "xl/" + target
    ss = ["".join(t.itertext()) for t in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS)]
    rows = []
    for r in ET.fromstring(z.read(path)).iter("{%s}row" % _NS["m"]):
        cells = {}
        for c in r.findall("m:c", _NS):
            v = c.find("m:v", _NS)
            if v is not None:
                cells[re.match(r"[A-Z]+", c.get("r")).group(0)] = ss[int(v.text)] if c.get("t") == "s" else v.text
        rows.append(cells)
    return rows


def parse_country(data: bytes, asof: str) -> dict[str, list[tuple[str, float]]]:
    """{'CRP_ERP_PH': [(asof, 6.69)], ...} for CGI's countries. `asof` (ISO date) is the file's last-modified date:
    the sheet's own "date of update" cell is stale (it still reads 2021)."""
    rows = _sheet_by_name(_open(data), COUNTRY_SHEET)
    hi = next((i for i, r in enumerate(rows) if (r.get("A") or "").strip() == "Country"), None)
    if hi is None:
        raise ValueError("layout changed: header row 'Country' not found")
    header = rows[hi]
    by_text: dict[str, str] = {}
    for col, text in header.items():
        by_text.setdefault((text or "").strip(), col)     # first match: the later "...2" columns are the CDS version
    cols = {}
    for pre, (text, _lo, _hi) in COUNTRY_COLS.items():
        if text not in by_text:
            raise ValueError(f"layout changed: column {text!r} not found in the header row")
        cols[pre] = by_text[text]
    byname = {(r.get("A") or "").strip(): r for r in rows[hi + 1:]}
    out: dict[str, list[tuple[str, float]]] = {}
    for code, name in COUNTRY_MAP.items():
        row = byname.get(name)
        if row is None:
            raise ValueError(f"layout changed: country {name!r} not found")
        for pre, col in cols.items():
            v = _num(row.get(col))
            if v is None:
                continue
            v *= 100.0
            _t, lo, hi_ = COUNTRY_COLS[pre]
            if not (lo <= v <= hi_):
                raise ValueError(f"{pre}_{code}: {v} outside {lo}..{hi_}")
            out[f"{pre}_{code}"] = [(asof, round(v, 4))]
    return out
