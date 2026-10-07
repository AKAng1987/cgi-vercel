import { AxisAnchor, AxisDriver, AxisDrivers, DriverLevel, MarkovAxis } from "@/lib/types";
import { flipTo, stateWord } from "@/lib/regimeView";

const ORDER: MarkovAxis[] = ["liquidity", "credit", "growth", "inflation"];
const LABEL: Record<MarkovAxis, string> = { liquidity: "Liquidity", credit: "Credit", growth: "Growth", inflation: "Inflation" };
const CURVE_WORD: Record<string, string> = {
  bull_steep: "bull steepener", bear_steep: "bear steepener", bull_flat: "bull flattener", bear_flat: "bear flattener",
};
const TH = "px-2 py-1 text-[0.62rem] font-normal uppercase tracking-wide text-slate-500";
const TD = "px-2 py-1 text-[0.74rem]";

function kindOf(name: string): string {
  if (/- Fed target/.test(name)) return "spread";
  if (/\(level\)|\(k\)|y\/y/.test(name)) return "level";
  if (/13w/.test(name)) return "13w chg";
  if (/3m %|3m chg/.test(name)) return "3m chg";
  if (/m\/m/.test(name)) return "vs last print";
  if (/30d/.test(name)) return "30d chg";
  if (/regime/i.test(name)) return "30d pattern";
  return "";
}
function shortName(name: string): string {
  return name.replace(/ 30d.*| 13w.*| 3m %| 3m chg| \(level\)| \(k\)| m\/m.*/, "").replace(" - Fed target", " − Fed target").replace("Curve regime", "Curve");
}
function fmt(v: number | null | undefined, name: string): string {
  if (v === null || v === undefined) return "—";
  const dp = Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 10 ? 1 : 2;
  const signed = /chg|%|target/.test(name) && !/y\/y/.test(name);
  return `${signed && v > 0 ? "+" : ""}${v.toFixed(dp)}${name.includes("%") ? "%" : ""}`;
}
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
/** "Sep print" for a monthly/weekly reading at least 20 days old; daily series read as of now, so no tag. */
function printTag(readingOf: string | null | undefined, asOf: string): string | null {
  if (!readingOf) return null;
  const days = (Date.parse(asOf) - Date.parse(readingOf)) / 86400000;
  return days >= 20 ? `${MONTHS[Number(readingOf.slice(5, 7)) - 1]} print` : null;
}

// Treasury yields here are the US Treasury's official daily curve (constant maturity), which sits a few bp
// from TradingView's traded-bill quote of the same name.
const LEVEL_NAME: Record<string, string> = {
  US03MY: "3m (Treasury)", US02Y: "2y (Treasury)", US05Y: "5y (Treasury)", US10Y: "10y (Treasury)",
  DFEDTARU: "Fed target", UNRATE: "rate",
};
function fmtLevel(v: number, unit: DriverLevel["unit"]): string {
  return unit === "%" ? `${v.toFixed(2)}%` : unit === "k" ? `${v.toFixed(1)}k` : v.toFixed(1);
}
function LevelLine({ levels }: { levels?: DriverLevel[] }) {
  if (!levels || levels.length === 0) return null;
  return (
    <div className="text-[0.6rem] font-normal text-slate-400">
      {levels.map((l) => (
        <div key={l.symbol}>
          {LEVEL_NAME[l.symbol] ? `${LEVEL_NAME[l.symbol]} ` : ""}{fmtLevel(l.value, l.unit)}
          {l.prev !== null && l.unit !== "%" && <span className="text-slate-500"> (was {fmtLevel(l.prev, l.unit)})</span>}
        </div>
      ))}
    </div>
  );
}
function AnchorRows({ anchors }: { anchors?: AxisAnchor[] }) {
  if (!anchors || anchors.length === 0) return null;
  return (
    <>
      {anchors.map((a) => (
        <tr key={a.label} className="border-t border-slate-800/60 bg-slate-800/30">
          <td className={TD}><span className="font-semibold text-slate-100">{a.label}</span> <span className="text-[0.62rem] text-slate-500">headline</span></td>
          <td className={`${TD} text-right font-bold text-slate-100`}>
            {a.value === null ? "—" : `${a.value}${a.unit === "%" ? "%" : ""}`}
            {a.date && <div className="text-[0.6rem] font-normal text-slate-500">{a.date.length === 7 ? `${MONTHS[Number(a.date.slice(5, 7)) - 1]} print` : `since ${a.date}`}</div>}
          </td>
          <td className={`${TD} text-slate-400`} colSpan={3}>
            {a.prev !== null ? `was ${a.prev}${a.unit === "%" ? "%" : ""}` : ""} <span className="text-slate-600">· context, not scored</span>
          </td>
        </tr>
      ))}
    </>
  );
}

function pct(p: number | null | undefined): string {
  return p === null || p === undefined ? "—" : `${Math.round(p * 100)}%`;
}

function Row({ d, axis, flipUp, asOf }: { d: AxisDriver; axis: MarkovAxis; flipUp: boolean; asOf: string }) {
  const base = d.base_rate ?? null;
  const name = shortName(d.name);
  const kind = kindOf(d.name);
  const tag = printTag(d.reading_of, asOf);

  if (d.insufficient) {
    return (
      <tr className="border-t border-slate-800/60 text-slate-600">
        <td className={TD}><span className="font-medium text-slate-500">{name}</span> <span className="text-[0.62rem]">{kind}</span></td>
        <td className={`${TD} text-right`}>{fmt(d.current_value, d.name)}<LevelLine levels={d.levels} /></td>
        <td className={TD} colSpan={3}>not enough history yet (n={d.n}, needs 24)</td>
      </tr>
    );
  }

  if (d.categorical) {
    const b = d.buckets ?? {};
    const cur = d.current_bucket ?? "";
    const curB = b[cur];
    const tip = Object.entries(b).map(([k, v]) => `${CURVE_WORD[k] ?? k}: ${pct(v.p_flip)} (n=${v.n})`).join(" · ");
    const thin = !curB || curB.n < 8;
    return (
      <tr className="border-t border-slate-800/60" title={tip}>
        <td className={TD}><span className="font-medium text-slate-200">{name}</span> <span className="text-[0.62rem] text-slate-600">{kind}</span></td>
        <td className={`${TD} text-right font-semibold text-[var(--cgi-gold)]`} colSpan={2}>{CURVE_WORD[cur] ?? cur ?? "—"}</td>
        <td className={`${TD} text-right ${thin ? "text-slate-600" : "font-bold text-slate-100"}`}>{pct(curB?.p_flip)}{thin && <span className="ml-1 text-[0.6rem] font-normal">n={curB?.n ?? 0}</span>}</td>
        <td className={`${TD} text-right text-slate-500`}>{pct(base)}</td>
      </tr>
    );
  }

  const [t0, t1] = d.terciles ?? [null, null];
  const p = d.p_by_tercile ?? [null, null, null];
  const n = d.n_by_tercile ?? [0, 0, 0];
  const cur = d.current_tercile ?? null;
  const where = cur === 0 ? `low · below ${fmt(t0, d.name)}` : cur === 2 ? `high · above ${fmt(t1, d.name)}` : cur === 1 ? `mid · ${fmt(t0, d.name)} to ${fmt(t1, d.name)}` : "—";
  const pc = cur === null ? null : p[cur];
  const lift = pc !== null && base !== null && base > 0 ? pc / base : null;
  const tone = lift === null ? "text-slate-300" : lift >= 1.3 ? "font-bold text-[var(--cgi-gold)]" : lift <= 0.7 ? "text-slate-500" : "font-bold text-slate-100";
  const tip = `low ${pct(p[0])} (n=${n[0]}) · mid ${pct(p[1])} (n=${n[1]}) · high ${pct(p[2])} (n=${n[2]})`;
  return (
    <tr className="border-t border-slate-800/60" title={tip}>
      <td className={TD}><span className="font-medium text-slate-200">{name}</span> <span className="text-[0.62rem] text-slate-600">{kind}</span>{d.n < 40 && <span className="ml-1 text-[0.6rem] text-slate-600">n={d.n}</span>}</td>
      <td className={`${TD} text-right font-semibold text-slate-100`}>
        {fmt(d.current_value, d.name)}
        {tag && <div className="text-[0.6rem] font-normal text-slate-500">{tag}</div>}
        <LevelLine levels={d.levels} />
      </td>
      <td className={`${TD} text-slate-400`}>{where}</td>
      <td className={`${TD} text-right ${tone}`}>{pct(pc)}</td>
      <td className={`${TD} text-right text-slate-500`}>{pct(base)}</td>
    </tr>
  );
}

export function AxisDriversPanel({ drivers }: { drivers: { as_of: string; axes: Record<MarkovAxis, AxisDrivers> } | null }) {
  if (!drivers) return null;
  return (
    <section className="mb-6">
      <div className="mb-2 flex items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">What moves each axis</div>
        <div className="text-xs text-slate-500">
          how often the axis flipped within one release when the driver sat where it sits today · hover a row for all three thirds
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {ORDER.map((axis) => {
          const a = drivers.axes[axis];
          if (!a) return null;
          const c = a.current;
          const up = a.current_state === 1;
          const to = flipTo(axis, up);
          const word = `flips to ${to.word} ${to.arrow}`;
          const dir = c.conditioned_p_flip !== null && c.base_rate !== null ? c.conditioned_p_flip - c.base_rate : null;
          return (
            <div key={axis} className="rounded border border-slate-800 bg-slate-900/60 p-3">
              <div className="mb-2 flex items-baseline justify-between">
                <div className="text-sm font-bold text-slate-100">
                  {LABEL[axis]} <span className="text-slate-500">{up ? "↑" : "↓"} {stateWord(axis, up)}</span>
                  <span className="ml-2 text-[0.65rem] font-normal uppercase tracking-wide text-slate-500">{a.release_type} · {c.n_windows} windows</span>
                </div>
                <div className="text-xs text-slate-400">
                  {word} <span className="text-slate-200">{pct(c.base_rate)}</span> of the time
                  <span className="mx-1 text-slate-600">→</span>
                  today <span className={`font-bold ${dir !== null && Math.abs(dir) >= 0.08 ? "text-[var(--cgi-gold)]" : "text-slate-100"}`}>{pct(c.conditioned_p_flip)}</span>
                </div>
              </div>
              <table className="w-full border-collapse">
                <thead>
                  <tr>
                    <th className={`${TH} text-left`}>driver</th>
                    <th className={`${TH} text-right`}>now</th>
                    <th className={`${TH} text-left`}>sits in</th>
                    <th className={`${TH} text-right`}>{word} there</th>
                    <th className={`${TH} text-right`}>base</th>
                  </tr>
                </thead>
                <tbody>
                  <AnchorRows anchors={a.anchors} />
                  {c.drivers.map((d) => <Row key={d.name} d={d} axis={axis} flipUp={up} asOf={drivers.as_of} />)}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>
    </section>
  );
}
