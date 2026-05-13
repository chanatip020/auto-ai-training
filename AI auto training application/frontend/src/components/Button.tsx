import type { ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
}

const variants: Record<Variant, string> = {
  primary:
    'bg-blue-600 hover:bg-blue-700 text-white border-transparent shadow-sm',
  secondary:
    'bg-white hover:bg-slate-50 text-slate-900 border-slate-300 shadow-sm',
  ghost:
    'bg-transparent hover:bg-slate-100 text-slate-700 border-transparent',
  danger:
    'bg-red-600 hover:bg-red-700 text-white border-transparent shadow-sm',
};

export function Button({
  variant = 'primary',
  loading,
  disabled,
  className = '',
  children,
  ...rest
}: Props) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={
        'inline-flex items-center justify-center gap-2 rounded-md border ' +
        'px-3 py-1.5 text-sm font-medium transition ' +
        'disabled:opacity-50 disabled:cursor-not-allowed ' +
        variants[variant] + ' ' + className
      }
    >
      {loading && (
        <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {children}
    </button>
  );
}
