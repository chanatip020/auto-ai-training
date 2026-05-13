import { Link, useNavigate, useParams } from 'react-router-dom';
import { Button } from '../../components/Button';
import { Card, CardBody, CardHeader } from '../../components/Card';
import { FullSpinner } from '../../components/Spinner';
import { PageHeader } from '../../components/PageHeader';
import { StatusPill } from '../../components/StatusPill';
import { formatTime, timeAgo } from '../../lib/format';
import { useDeleteProject, useProject, useTimeline } from './api';

export function ProjectDetailPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const project = useProject(id);
  const timeline = useTimeline(id);
  const del = useDeleteProject();

  if (project.isLoading) return <FullSpinner label="Loading project" />;
  if (project.error || !project.data) {
    return <div className="text-sm text-red-700">Project not found.</div>;
  }
  const p = project.data;

  return (
    <div>
      <PageHeader
        title={p.name}
        subtitle={p.description || '— no description —'}
        action={
          <>
            <StatusPill status={p.status} />
            <Button
              variant="danger"
              loading={del.isPending}
              onClick={async () => {
                if (!confirm('Delete this project? It will be hidden but data is kept.')) return;
                await del.mutateAsync(id);
                navigate('/');
              }}
            >
              Delete
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="What next?" />
          <CardBody className="space-y-2">
            <NextStep
              label="Upload a dataset"
              hint="ZIP or loose files. We'll detect the format automatically."
              to={`/projects/${id}/dataset`}
              done={p.status !== 'created'}
            />
            <NextStep
              label="Convert to YOLO format"
              hint="Pairs images with labels and writes data.yaml + 70/20/10 split."
              to={`/projects/${id}/dataset`}
              done={['dataset_analyzed', 'ready_for_training', 'training', 'completed'].includes(p.status)}
            />
            <NextStep
              label="Analyze + recommendations"
              hint="Health score, class balance, missing labels, training-param suggestions."
              to={`/projects/${id}/dataset`}
              done={['ready_for_training', 'training', 'completed'].includes(p.status)}
            />
            <NextStep
              label="Start training"
              hint="Live loss / mAP charts and downloadable best.pt."
              to={`/projects/${id}/train`}
              done={['training', 'completed'].includes(p.status)}
            />
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Project" />
          <CardBody className="space-y-2 text-xs text-slate-600">
            <Row label="Model" value={`${p.model_family} / ${p.task_type}`} />
            <Row label="Status" value={p.status} />
            <Row label="Created" value={`${formatTime(p.created_at)} (${timeAgo(p.created_at)})`} />
            <Row label="Updated" value={timeAgo(p.updated_at)} />
            <Row label="Project ID" value={p.id} mono />
          </CardBody>
        </Card>
      </div>

      <div className="mt-4">
        <Card>
          <CardHeader title="Timeline" subtitle="Append-only audit log of project events." />
          <CardBody>
            {timeline.isLoading ? (
              <FullSpinner />
            ) : !timeline.data || timeline.data.items.length === 0 ? (
              <p className="text-sm text-slate-500">No events yet.</p>
            ) : (
              <ol className="space-y-2">
                {timeline.data.items.map((it) => (
                  <li key={it.id} className="flex gap-3 text-xs">
                    <span className="w-32 shrink-0 text-slate-400">{timeAgo(it.created_at)}</span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono">{it.event}</span>
                    <span className="truncate text-slate-600">{summarize(it.payload)}</span>
                  </li>
                ))}
              </ol>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function NextStep({
  label, hint, to, done,
}: { label: string; hint: string; to: string; done: boolean }) {
  return (
    <Link
      to={to}
      className="flex items-start gap-3 rounded-md border border-slate-200 px-3 py-2 transition hover:border-blue-400 hover:bg-blue-50/40"
    >
      <span
        className={
          'mt-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-bold ' +
          (done ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500')
        }
      >
        {done ? '✓' : '•'}
      </span>
      <div className="flex-1">
        <div className="text-sm font-medium text-slate-900">{label}</div>
        <div className="text-xs text-slate-500">{hint}</div>
      </div>
    </Link>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-slate-500">{label}</span>
      <span className={'truncate text-slate-900 ' + (mono ? 'font-mono text-[11px]' : '')}>
        {value}
      </span>
    </div>
  );
}

function summarize(payload: Record<string, unknown>): string {
  if (!payload || Object.keys(payload).length === 0) return '';
  return Object.entries(payload)
    .slice(0, 4)
    .map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : String(v)}`)
    .join('  ');
}
