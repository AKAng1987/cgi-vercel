/** Formatting helpers for the Philippines tab. Pesos are shown in short form; EDGE filings link back to the original. */

export function peso(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const a = Math.abs(v);
  const s = v < 0 ? "-" : "";
  if (a >= 1e12) return `${s}₱${(a / 1e12).toFixed(2)}T`;
  if (a >= 1e9) return `${s}₱${(a / 1e9).toFixed(a >= 1e11 ? 0 : 1)}B`;
  if (a >= 1e6) return `${s}₱${(a / 1e6).toFixed(a >= 1e8 ? 0 : 1)}M`;
  if (a >= 1e3) return `${s}₱${(a / 1e3).toFixed(0)}K`;
  return `${s}₱${a.toFixed(0)}`;
}

export function pct(v: number | null | undefined, digits = 1, sign = true): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${sign && v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

export function num(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function price(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v >= 100 ? v.toFixed(1) : v >= 10 ? v.toFixed(2) : v.toFixed(3);
}

export const edgeLink = (edgeNo: string) => `https://edge.pse.com.ph/openDiscViewer.do?edge_no=${edgeNo}`;
export const tvSymbol = (s: string) => `PSE:${s}`;

export const CHIPS: { key: string; label: string }[] = [
  { key: "all", label: "All" },
  { key: "material", label: "Material info" },
  { key: "buyback", label: "Buy-back" },
  { key: "insider", label: "Insider (13-1)" },
  { key: "dividend", label: "Dividend" },
  { key: "index", label: "Index (MSCI, FTSE, PSEi)" },
  { key: "ownership", label: "Ownership (17-8, 17-6)" },
  { key: "corporate", label: "Corporate action" },
  { key: "meeting", label: "Meetings & briefings" },
  { key: "people", label: "Directors & officers" },
  { key: "press", label: "Press release" },
];

/** short day label "Oct 30" from an ISO date or datetime */
export function dayLabel(iso: string): string {
  const d = new Date(iso.slice(0, 10) + "T00:00:00Z");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}
