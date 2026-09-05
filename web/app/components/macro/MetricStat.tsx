/**
 * Small current-value + delta stat display -- equivalent of Streamlit's
 * st.metric(), used for Fed Funds Range, Lending Standards, GDP latest
 * print (app.py:2115-2120, 2412-2419, 2478-2482).
 */
export function MetricStat({
  label,
  value,
  delta,
  help,
}: {
  label: string;
  value: string;
  delta?: string | null;
  help?: string;
}) {
  const deltaColor = delta?.trim().startsWith("-") ? "text-red-400" : delta ? "text-emerald-400" : "";
  return (
    <div className="mb-2">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-xl font-semibold text-slate-100">{value}</div>
      {delta && <div className={`text-xs ${deltaColor}`}>{delta}</div>}
      {help && <div className="text-[0.65rem] text-slate-600">{help}</div>}
    </div>
  );
}
