export function SectionSkeleton({ lines = 2 }: { lines?: number }) {
  return (
    <div className="animate-pulse">
      <div className="mb-2 h-3 w-56 rounded bg-slate-800" />
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="mb-3 h-48 rounded-lg border border-slate-800 bg-slate-900" />
      ))}
    </div>
  );
}
