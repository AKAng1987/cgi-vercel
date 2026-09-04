export function DateHeader({
  asOf,
  generatedAt,
}: {
  asOf: string;
  generatedAt: string;
}) {
  const asOfDate = new Date(`${asOf}T00:00:00Z`);
  const formatted = asOfDate.toLocaleDateString("en-US", {
    weekday: "long",
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
  const generated = new Date(generatedAt).toLocaleString("en-US", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  return (
    <div className="mb-2 text-xs text-slate-500">
      Data date: <b className="text-slate-400">{formatted}</b>
      <span className="ml-2 text-slate-600">
        · report generated {generated} UTC
      </span>
    </div>
  );
}
