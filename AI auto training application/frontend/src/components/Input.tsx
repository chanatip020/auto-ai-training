import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';

export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-700">{label}</span>
      {children}
      {error ? (
        <span className="mt-1 block text-xs text-red-600">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-xs text-slate-500">{hint}</span>
      ) : null}
    </label>
  );
}

const baseInput =
  'block w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm ' +
  'shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none ' +
  'focus:ring-1 focus:ring-blue-500 disabled:bg-slate-50 disabled:text-slate-500';

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={baseInput + ' ' + (props.className || '')} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={baseInput + ' ' + (props.className || '')} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={baseInput + ' ' + (props.className || '')} />;
}
