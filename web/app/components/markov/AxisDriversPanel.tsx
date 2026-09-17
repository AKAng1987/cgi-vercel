import { AxisDriver, AxisDrivers, MarkovAxis } from "@/lib/types";

const ORDER: MarkovAxis[] = ["liquidity", "credit", "growth", "inflation"];
const LABEL: Record<MarkovAxis, string> = { liquidity: "Liquidity", credit: "Credit", growth: "Growth", inflation: "Inflation" };
const FLIP_WORD: Record<MarkovAxis, [string, string]> = {
  liquidity: ["cuts", "hikes"], credit: ["loosens", "tightens"], growth: ["turns up", "turns down"], inflation: ["turns up", "cools"],
};
const CURVE_WORD: Record<string, string> = {
  bull_steep: "bull steepener", bear_steep: "bear steepener", bull_flat: "bull flattener", bear_flat: "bear flattener",
};
const TH = "px-2 py-1 text-[0.62rem] font-normal uppercase tracking-wide text-slate-500";
const TD = "px-2 py-1 text-[0.74rem]";

function kindOf(name: string): string {
  if (/\(level\)|\(k\)|y\/y|- Fed target/.test(name)) return "level";
  if (/13w/.test(name)) return "13w chg";
  if (/m\/m/.test(name)) return "vs last print";
  if (/30d/.test(name)) return "30d chg";
  if (/regime/i.test(name)) return "30d pattern";
  return "";
}
function shortName(name: string): string {
  return name.replace(/ 30d.*| 13w.*| \(level\)| \(k\)| m\/m.*| - Fed target/, "").replace("Curve regime", "Curve");
}
function fmt(v: number | null | undefined, name: string): string {
  if (v === null || v === undefined) return "—";
  const dp = Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 10 ? 1 : 2;
  const signed = /chg|%|target/.test(name) && !/y\/y/.test(name);
  return `${signed && v > 0 ? "+" : ""}${v.toFixed(dp)}${name.includes("%") ? "%" : ""}`;
}
function pct(p: number | null | undefined): string {
  return p === null || p === undefined ? "—" : `${Math.round(p * 100)}%`;
}

function Row({ d, axis, flipUp }: { d: AxisDriver; axis: MarkovAxis; flipUp: boolean }) {
  const base = d.base_rate ?? null;
  const name = shortName(d.name);
  const kind = kindOf(d.name);

  if (d.insufficient) {
    return (
      <tr className="border-t border-slate-800/60 text-slate-600">
        <td className={TD}><span className="font-medium text-slate-500">{name}</span> <span className="text-[0.62rem]">{kind}</span></td>
        <td className={`${TD} text-right`}>{fmt(d.current_value, d.name)}</td>
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
        <td className={`${TD} text-right font-semibold text-[#FCD34D]`} colSpan={2}>{CURVE_WORD[cur] ?? cur ?? "—"}</td>
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
  const tone = lift === null ? "text-slate-300" : lift >= 1.3 ? "font-bold text-[#FCD34D]" : lift <= 0.7 ? "text-slate-500" : "font-bold text-slate-100";
  const tip = `low ${pct(p[0])} (n=${n[0]}) · mid ${pct(p[1])} (n=${n[1]}) · high ${pct(p[2])} (n=${n[2]})`;
  return (
    <tr className="border-t border-slate-800/60" title={tip}>
      <td className={TD}><span className="font-medium text-slate-200">{name}</span> <span className="text-[0.62rem] text-slate-600">{kind}</span>{d.n < 40 && <span className="ml-1 text-[0.6rem] text-slate-600">n={d.n}</span>}</td>
      <td className={`${TD} text-right font-semibold text-slate-100`}>{fmt(d.current_value, d.name)}</td>
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
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">What moves each axis</div>
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
          const word = FLIP_WORD[axis][up ? 1 : 0];
          const dir = c.conditioned_p_flip !== null && c.base_rate !== null ? c.conditioned_p_flip - c.base_rate : null;
          return (
            <div key={axis} className="rounded border border-slate-800 bg-slate-900/60 p-3">
              <div className="mb-2 flex items-baseline justify-between">
                <div className="text-sm font-bold text-slate-100">
                  {LABEL[axis]} <span className="text-slate-500">{up ? "↑" : "↓"}</span>
                  <span className="ml-2 text-[0.65rem] font-normal uppercase tracking-wide text-slate-500">{a.release_type} · {c.n_windows} windows</span>
                </div>
                <div className="text-xs text-slate-400">
                  {word} <span className="text-slate-200">{pct(c.base_rate)}</span> of the time
                  <span className="mx-1 text-slate-600">→</span>
                  today <span className={`font-bold ${dir !== null && Math.abs(dir) >= 0.08 ? "text-[#FCD34D]" : "text-slate-100"}`}>{pct(c.conditioned_p_flip)}</span>
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
                  {c.drivers.map((d) => <Row key={d.name} d={d} axis={axis} flipUp={up} />)}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>
    </section>
  );
}
