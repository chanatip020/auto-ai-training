export function Spinner({ size = 16 }: { size?: number }) {
  return (
    <span
      className="inline-block animate-spin rounded-full border-2 border-slate-400 border-t-transparent"
      style={{ width: size, height: size }}
    />
  );
}

export function FullSpinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-12 text-slate-500">
      <Spinner size={20} />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}
