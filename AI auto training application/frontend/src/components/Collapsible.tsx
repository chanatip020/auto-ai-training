import { useState, type ReactNode } from 'react';

export function Collapsible({
  title,
  subtitle,
  defaultOpen = false,
  children,
}: {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="overflow-hidden rounded-md border border-slate-200">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 bg-slate-50 px-3 py-2 text-left hover:bg-slate-100"
      >
        <div>
          <div className="text-sm font-medium text-slate-900">{title}</div>
          {subtitle && <div className="text-[11px] text-slate-500">{subtitle}</div>}
        </div>
        <span
          className="text-xs text-slate-400 transition"
          style={{ transform: open ? 'rotate(90deg)' : 'none' }}
        >
          ▶
        </span>
      </button>
      {open && <div className="border-t border-slate-200 p-3">{children}</div>}
    </div>
  );
}
