export function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-1 text-[0.62rem] uppercase tracking-[2px] text-slate-500">
      {children}
    </div>
  );
}

export function ErrorCard({ label, message }: { label: string; message: string }) {
  return (
    <div className="rounded-lg border border-red-900 bg-red-950/30 p-3 text-sm">
      <span className="font-medium text-red-400">{label} unavailable</span>
      <p className="mt-1 text-xs text-slate-500">{message}</p>
    </div>
  );
}
