import { AxisDriver, AxisDrivers, MarkovAxis } from "@/lib/types";

const ORDER: MarkovAxis[] = ["liquidity", "credit", "growth", "inflation"];
const LABEL: Record<MarkovAxis, string> = { liquidity: "Liquidity", credit: "Credit", growth: "Growth", inflation: "Inflation" };
const FLIP_WORD: Record<MarkovAxis, [string, string]> = {
  liquidity: ["cut", "hiked"], credit: ["loosened", "tightened"], growth: ["turned up", "turned down"], inflation: ["turned up", "cooled"],
};
const CURVE_WORD: Record<string, string> = {
  bull_steep: "bull steepener (short end fell)", bear_steep: "bear steepener (long end rose)",
  bull_flat: "bull flattener (long end fell)", bear_flat: "bear flattener (short end rose)",
};

function kindOf(name: string): string {
  if (/\(level\)|\(k\)|y\/y/.test(name)) return "level";
  if (/13w/.test(name)) return "13-week change";
  if (/m\/m/.test(name)) return "change since last print";
  if (/30d/.test(name)) return "30-day change";
  if (/- Fed target/.test(name)) return "level (spread)";
  if (/regime/i.test(name)) return "30-day pattern";
  return "";
}
function fmt(v: number | null | undefined, name: string): string {
  if (v === null || v === undefined) return "—";
  const pctish = name.includes("%");
  const dp = Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 10 ? 1 : 2;
  return `${v > 0 && !name.includes("(level)") && !name.includes("(k)") && !name.includes("y/y") ? "+" : ""}${v.toFixed(dp)}${pctish ? "%" : ""}`;
}
function pct(p: number | null | undefined): string {
  return p === null || p === undefined ? "—" : `${Math.round(p * 100)}%`;
}

function Tercile({ d, axis, flipUp }: { d: AxisDriver; axis: MarkovAxis; flipUp: boolean }) {
  const [t0, t1] = d.terciles ?? [null, null];
  const p = d.p_by_tercile ?? [null, null, null];
  const n = d.n_by_tercile ?? [0, 0, 0];
  const base = d.base_rate ?? null;
  const cur = d.current_tercile;
  const word = FLIP_WORD[axis][flipUp ? 1 : 0];
  const cells: { label: string; p: number | null; n: number }[] = [
    { label: `below ${fmt(t0, d.name)}`, p: p[0], n: n[0] },
    { label: `${fmt(t0, d.name)} to ${fmt(t1, d.name)}`, p: p[1], n: n[1] },
    { label: `above ${fmt(t1, d.name)}`, p: p[2], n: n[2] },
  ];
  const best = cells.reduce((m, c, i) => (c.p !== null && (m < 0 || (c.p > (cells[m].p ?? -1))) ? i : m), -1);
  return (
    <div className="border-t border-slate-800/60 py-1.5">
      <div className="flex flex-wrap items-baseline gap-x-2 text-[0.74rem]">
        <span className="font-semibold text-slate-200">{d.name.replace(/ 30d.*| 13w.*| \(level\)| \(k\)/, "")}</span>
        <span className="text-[0.62rem] uppercase tracking-wide text-slate-600">{kindOf(d.name)}</span>
        <span className="text-slate-500">now</span>
        <span className="font-bold text-slate-100">{fmt(d.current_value, d.name)}</span>
        {d.n < 40 && <span className="text-[0.62rem] text-slate-600">n={d.n}</span>}
      </div>
      <div className="mt-1 grid grid-cols-3 gap-1">
        {cells.map((c, i) => {
          const isCur = cur === i;
          const strong = i === best && c.p !== null && base !== null && c.p >= base * 1.3;
          return (
            <div
              key={i}
              className={`rounded px-1.5 py-1 text-[0.68rem] leading-tight ${isCur ? "bg-[#2a2410] ring-1 ring-[#FCD34D]/60" : "bg-slate-950/60"}`}
              title={`${c.n} windows`}
            >
              <div className="text-slate-500">{c.label}</div>
              <div className={`text-sm font-bold ${strong ? "text-[#FCD34D]" : isCur ? "text-slate-100" : "text-slate-300"}`}>
                {pct(c.p)}
                {strong && <span className="ml-1 text-[0.6rem] font-normal text-[#FCD34D]/80">{word}-prone</span>}
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-0.5 text-[0.62rem] text-slate-600">base {pct(base)} · share of windows in which the axis {word} within one release</div>
    </div>
  );
}

function Categorical({ d, axis, flipUp }: { d: AxisDriver; axis: MarkovAxis; flipUp: boolean }) {
  const word = FLIP_WORD[axis][flipUp ? 1 : 0];
  const b = d.buckets ?? {};
  return (
    <div className="border-t border-slate-800/60 py-1.5">
      <div className="flex flex-wrap items-baseline gap-x-2 text-[0.74rem]">
        <span className="font-semibold text-slate-200">{d.name.replace(/ 30d.*/, "")}</span>
        <span className="text-[0.62rem] uppercase tracking-wide text-slate-600">{kindOf(d.name)}</span>
        <span className="text-slate-500">now</span>
        <span className="font-bold text-[#FCD34D]">{CURVE_WORD[d.current_bucket ?? ""] ?? d.current_bucket ?? "—"}</span>
      </div>
      <div className="mt-1 grid grid-cols-4 gap-1">
        {Object.entries(b).map(([k, v]) => (
          <div key={k} className={`rounded px-1.5 py-1 text-[0.68rem] leading-tight ${d.current_bucket === k ? "bg-[#2a2410] ring-1 ring-[#FCD34D]/60" : "bg-slate-950/60"}`} title={`${v.n} windows`}>
            <div className="text-slate-500">{k.replace("_", " ")}</div>
            <div className={`text-sm font-bold ${v.n < 8 ? "text-slate-600" : "text-slate-200"}`}>{pct(v.p_flip)}<span className="ml-1 text-[0.6rem] font-normal text-slate-600">n={v.n}</span></div>
          </div>
        ))}
      </div>
      <div className="mt-0.5 text-[0.62rem] text-slate-600">base {pct(d.base_rate)} · which end of the curve moved over the last 30 days · labels with n&lt;8 are shown but not counted</div>
    </div>
  );
}

export function AxisDriversPanel({ drivers }: { drivers: { as_of: string; axes: Record<MarkovAxis, AxisDrivers> } | null }) {
  if (!drivers) return null;
  return (
    <section className="mb-6">
      <div className="mb-2 flex items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">What moves each axis</div>
        <div className="text-xs text-slate-500">
          each driver&apos;s history is cut into thirds; the number is how often the axis flipped within one release when the driver sat in that third · today&apos;s third is boxed
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
              <div className="flex items-baseline justify-between">
                <div className="text-sm font-bold text-slate-100">
                  {LABEL[axis]} <span className="text-slate-500">{up ? "↑" : "↓"}</span>
                  <span className="ml-2 text-[0.68rem] font-normal uppercase tracking-wide text-slate-500">{a.release_type} · {a.cadence_days}d windows · {c.n_windows} windows</span>
                </div>
                <div className="text-xs text-slate-400">
                  {word} in <span className="text-slate-200">{pct(c.base_rate)}</span> of windows historically
                  <span className="mx-1 text-slate-600">→</span>
                  given today&apos;s drivers <span className={`font-bold ${dir !== null && Math.abs(dir) >= 0.08 ? "text-[#FCD34D]" : "text-slate-100"}`}>{pct(c.conditioned_p_flip)}</span>
                </div>
              </div>
              <div className="mt-2">
                {c.drivers.map((d) =>
                  d.insufficient ? (
                    <div key={d.name} className="border-t border-slate-800/60 py-1.5 text-[0.72rem] text-slate-600">
                      <span className="font-semibold text-slate-500">{d.name.replace(/ 30d.*| 13w.*| \(level\)/, "")}</span> · now {fmt(d.current_value, d.name)} · not enough history yet (n={d.n}, needs 24)
                    </div>
                  ) : d.categorical ? (
                    <Categorical key={d.name} d={d} axis={axis} flipUp={up} />
                  ) : (
                    <Tercile key={d.name} d={d} axis={axis} flipUp={up} />
                  )
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
