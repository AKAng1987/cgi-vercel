import { PhResponse } from "@/lib/types";
import { pctColor } from "@/lib/regimeConstants";
import { dayLabel, pct } from "./phFormat";

function Stat({ label, children, sub }: { label: string; children: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="min-w-[8rem]">
      <div className="text-[0.6rem] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-lg font-bold text-slate-100">{children}</div>
      {sub && <div className="text-[0.68rem] text-slate-500">{sub}</div>}
    </div>
  );
}

/** One strip: the PSEi, the peso, the BSP, and what CGI's regime says about Philippine equities and the peso. */
export function PhHeader({ d }: { d: PhResponse }) {
  const h = d.header;
  const ix = h.psei;
  const eq = h.equity;
  const rr = h.regime_ranking as { best?: { regime?: string }; worst?: { regime?: string } } | null;
  const fx = h.usdphp;
  const pol = h.policy;
  return (
    <section className="mb-4 rounded border border-slate-800 bg-slate-900/50 p-3">
      <div className="flex flex-wrap items-start gap-x-8 gap-y-3">
        <Stat
          label="PSEi"
          sub={ix ? (
            <span>
              <span style={{ color: pctColor(ix.w) }}>{pct(ix.w)} 1W</span> · <span style={{ color: pctColor(ix.m) }}>{pct(ix.m)} 1M</span> ·{" "}
              <span style={{ color: pctColor(ix.y) }}>{pct(ix.y)} YTD</span>
            </span>
          ) : "index not loaded"}
        >
          {ix?.c != null ? ix.c.toLocaleString("en-US", { maximumFractionDigits: 0 }) : "—"}
        </Stat>
        <Stat
          label="USD / PHP"
          sub={fx ? <span>{fx.local_3m ? `peso ${fx.local_3m} over 3M` : ""}{fx.ret_1m != null ? ` · ${pct(fx.ret_1m)} 1M` : ""}</span> : undefined}
        >
          {fx?.last != null ? fx.last.toFixed(2) : "—"}
        </Stat>
        <Stat
          label="BSP policy rate"
          sub={<span>next meeting {h.bsp.next ? dayLabel(h.bsp.next) : "not published"}{pol?.change_since_prior ? ` · last move ${pol.change_since_prior > 0 ? "+" : ""}${(pol.change_since_prior * 100).toFixed(0)}bp` : ""}</span>}
        >
          {pol ? `${pol.latest.toFixed(2)}%` : "—"}
        </Stat>
        <Stat
          label="CGI regime"
          sub={<span>Compass {h.compass_q} · Grid {h.grid_q}</span>}
        >
          {h.regime}
        </Stat>
        <Stat
          label={`EPHE in ${h.regime}`}
          sub={eq && eq.occurrences ? <span>n {eq.occurrences} · hit {eq.hit_rate != null ? `${Math.round(eq.hit_rate * (eq.hit_rate <= 1 ? 100 : 1))}%` : "—"}{rr?.best?.regime ? ` · best ${rr.best.regime}` : ""}{rr?.worst?.regime ? ` · worst ${rr.worst.regime}` : ""}</span> : "no read"}
        >
          <span style={{ color: pctColor(eq?.avg_return_pct) }}>{eq?.avg_return_pct != null ? pct(eq.avg_return_pct, 2) : "—"}</span>
        </Stat>
        {h.currency && (h.currency as { local?: string; avg_return_pct?: number; occurrences?: number }).occurrences ? (
          <Stat
            label={`USD/PHP in ${h.regime}`}
            sub={<span>n {(h.currency as { occurrences?: number }).occurrences} · average {pct((h.currency as { avg_return_pct?: number }).avg_return_pct, 2)} for USD</span>}
          >
            peso {(h.currency as { local?: string }).local ?? "—"}
          </Stat>
        ) : null}
        {h.risk_premium && (
          <Stat label="Equity risk premium" sub={<span>country part {h.risk_premium.country_premium_pct?.toFixed(2)}% (Damodaran)</span>}>
            {h.risk_premium.erp_pct?.toFixed(2)}%
          </Stat>
        )}
      </div>
      <p className="mt-2 text-[0.65rem] leading-relaxed text-slate-600">
        The regime read is CGI&apos;s history of EPHE in this regime: a small sample, not a signal. Everything below describes what has happened or been filed.
      </p>
    </section>
  );
}
