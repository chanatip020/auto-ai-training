import type { JobStatus, ProjectStatus } from '../lib/types';

const projectColor: Record<ProjectStatus, string> = {
  created: 'bg-slate-100 text-slate-700 ring-slate-200',
  dataset_uploaded: 'bg-blue-50 text-blue-700 ring-blue-200',
  dataset_analyzed: 'bg-teal-50 text-teal-700 ring-teal-200',
  ready_for_training: 'bg-green-50 text-green-700 ring-green-200',
  training: 'bg-amber-50 text-amber-700 ring-amber-200',
  completed: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  failed: 'bg-red-50 text-red-700 ring-red-200',
};

const jobColor: Record<JobStatus, string> = {
  pending: 'bg-slate-100 text-slate-700 ring-slate-200',
  running: 'bg-amber-50 text-amber-700 ring-amber-200',
  succeeded: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  failed: 'bg-red-50 text-red-700 ring-red-200',
  cancelled: 'bg-slate-100 text-slate-600 ring-slate-200',
};

const labels: Record<string, string> = {
  created: 'Created',
  dataset_uploaded: 'Uploaded',
  dataset_analyzed: 'Analyzed',
  ready_for_training: 'Ready',
  training: 'Training',
  completed: 'Completed',
  failed: 'Failed',
  pending: 'Pending',
  running: 'Running',
  succeeded: 'Succeeded',
  cancelled: 'Cancelled',
};

export function StatusPill({ status }: { status: ProjectStatus | JobStatus }) {
  const cls = (projectColor as any)[status] || (jobColor as any)[status] ||
    'bg-slate-100 text-slate-700 ring-slate-200';
  return (
    <span
      className={
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ' +
        cls
      }
    >
      {labels[status] || status}
    </span>
  );
}
