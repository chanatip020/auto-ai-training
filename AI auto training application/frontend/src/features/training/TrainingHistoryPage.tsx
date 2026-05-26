import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Button } from '../../components/Button';
import { Card, CardBody, CardHeader } from '../../components/Card';
import { FullSpinner } from '../../components/Spinner';
import { PageHeader } from '../../components/PageHeader';
import { StatusPill } from '../../components/StatusPill';
import { num, timeAgo } from '../../lib/format';
import { useProject } from '../projects/api';
import { useTrainingHistory, type TrainingHistoryItem } from './api';
import { OverlayMetricsChart } from './OverlayMetricsChart';

type SortKey = 'created_at' | 'best_metric' | 'epochs' | 'model';
type SortDir = 'asc' | 'desc';

export function TrainingHistoryPage() {
  const { id: projectId = '' } = useParams();
  const project = useProject(projectId);
  const history = useTrainingHistory(projectId, { limit: 200 });
  const navigate = useNavigate();

  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [sortKey, setSortKey] = useState<SortKey>('created_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const rows = useMemo(() => {
    const all = history.data?.items ?? [];
    const filtered = statusFilter === 'all'
      ? all
      : all.filter((r) => r.status === statusFilter);
    const sorted = [...filtered].sort((a, b) => {
      const cmp = compareBy(a, b, sortKey);
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return sorted;
  }, [history.data, statusFilter, sortKey, sortDir]);

  function toggleSelect(id: string) {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else if (next.size < 2) next.add(id);
      else {
        // Replace the oldest selection (simple FIFO of 2)
        const [first] = next;
        next.delete(first);
        next.add(id);
      }
      return next;
    });
  }

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir('desc'); }
  }

  const compareItems = selected.size === 2
    ? rows.filter((r) => selected.has(r.id))
    : null;

  return (
    <div>
      <PageHeader
        title="Training history"
        subtitle={project.data ? `Project: ${project.data.name}` : ''}
        action={
          <Link to={`/projects/${projectId}/train`}>
            <Button>New training run</Button>
          </Link>
        }
      />

      <div className="mb-3 flex items-center gap-2">
        <label className="text-xs text-slate-600">Filter:</label>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs"
        >
          <option value="all">All</option>
          <option value="succeeded">Succeeded</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
          <option value="running">Running</option>
        </select>
        <div className="ml-auto text-xs text-slate-500">
          {selected.size === 2
            ? 'Comparing 2 runs below.'
            : selected.size === 1
            ? 'Pick one more row to compare.'
            : 'Tick up to 2 rows to compare.'}
        </div>
      </div>

      {history.isLoading && <FullSpinner label="Loading history" />}

      {history.data && rows.length === 0 && (
        <Card>
          <CardBody className="text-center text-sm text-slate-500">
            No training runs yet.{' '}
            <Link to={`/projects/${projectId}/train`} className="text-blue-600 underline">
              Start one
            </Link>
            .
          </CardBody>
        </Card>
      )}

      {rows.length > 0 && (
        <Card>
          <CardBody className="overflow-x-auto p-0">
            <table className="w-full text-xs">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-2 py-2"></th>
                  <th className="px-2 py-2 text-left">Status</th>
                  <Th onClick={() => toggleSort('model')} active={sortKey === 'model'} dir={sortDir}>Model</Th>
                  <Th onClick={() => toggleSort('epochs')} active={sortKey === 'epochs'} dir={sortDir}>Epochs</Th>
                  <Th onClick={() => toggleSort('best_metric')} active={sortKey === 'best_metric'} dir={sortDir}>Best mAP50-95</Th>
                  <th className="px-2 py-2 text-left">Preset</th>
                  <th className="px-2 py-2 text-left">Override</th>
                  <Th onClick={() => toggleSort('created_at')} active={sortKey === 'created_at'} dir={sortDir}>Started</Th>
                  <th className="px-2 py-2 text-left">Time</th>
                  <th className="px-2 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="px-2 py-2">
                      <input
                        type="checkbox"
                        checked={selected.has(r.id)}
                        onChange={() => toggleSelect(r.id)}
                      />
                    </td>
                    <td className="px-2 py-2"><StatusPill status={r.status} /></td>
                    <td className="px-2 py-2 font-mono">{String(r.params.model ?? '—')}</td>
                    <td className="px-2 py-2 font-mono">
                      {r.current_epoch ?? 0}/{r.total_epochs ?? '?'}
                    </td>
                    <td className="px-2 py-2 font-mono">{num(r.best_metric, 4)}</td>
                    <td className="px-2 py-2">{r.preset_source ?? '—'}</td>
                    <td className="px-2 py-2">{r.override_blockers ? '⚠' : ''}</td>
                    <td className="px-2 py-2">{timeAgo(r.started_at || r.created_at)}</td>
                    <td className="px-2 py-2">
                      {typeof r.summary?.total_time_s === 'number'
                        ? formatDuration(r.summary.total_time_s as number)
                        : '—'}
                    </td>
                    <td className="px-2 py-2 text-right">
                      <button
                        onClick={() => navigate(`/projects/${projectId}/train/${r.id}`)}
                        className="text-blue-600 hover:underline"
                      >
                        Open →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}

      {compareItems && compareItems.length === 2 && (
        <Card className="mt-4">
          <CardHeader title="Side-by-side comparison" subtitle="Param differences highlighted in blue." />
          <CardBody>
            <CompareTwo a={compareItems[0]} b={compareItems[1]} />
          </CardBody>
        </Card>
      )}

      {compareItems && compareItems.length === 2 && (
        <Card className="mt-4">
          <CardHeader
            title="Metrics overlay"
            subtitle="Loss / mAP curves of the two selected runs on one chart."
          />
          <CardBody>
            <OverlayMetricsChart
              runs={compareItems.map((r, i) => ({
                id: r.id,
                label: `${String.fromCharCode(65 + i)} · ${String(r.params.model ?? '?')}`
                       + ` · best ${num(r.best_metric, 3)}`,
              }))}
            />
          </CardBody>
        </Card>
      )}
    </div>
  );
}


// ---- helpers + small components ----

function compareBy(a: TrainingHistoryItem, b: TrainingHistoryItem, key: SortKey): number {
  switch (key) {
    case 'created_at':
      return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
    case 'best_metric': {
      const va = a.best_metric == null ? -1 : Number(a.best_metric);
      const vb = b.best_metric == null ? -1 : Number(b.best_metric);
      return va - vb;
    }
    case 'epochs':
      return (a.current_epoch ?? 0) - (b.current_epoch ?? 0);
    case 'model':
      return String(a.params.model ?? '').localeCompare(String(b.params.model ?? ''));
  }
}

function formatDuration(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  return `${(s / 3600).toFixed(1)}h`;
}

function Th({
  children, onClick, active, dir,
}: {
  children: React.ReactNode;
  onClick: () => void;
  active: boolean;
  dir: SortDir;
}) {
  return (
    <th
      onClick={onClick}
      className={
        'cursor-pointer select-none px-2 py-2 text-left hover:text-slate-900 ' +
        (active ? 'text-slate-900' : 'text-slate-600')
      }
    >
      {children}
      {active && <span className="ml-1 text-[10px]">{dir === 'asc' ? '▲' : '▼'}</span>}
    </th>
  );
}


function CompareTwo({ a, b }: { a: TrainingHistoryItem; b: TrainingHistoryItem }) {
  const allKeys = new Set<string>();
  Object.keys(a.params).forEach((k) => allKeys.add(k));
  Object.keys(b.params).forEach((k) => allKeys.add(k));
  const keys = [...allKeys].sort();

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            <th className="px-2 py-2 text-left">Parameter</th>
            <th className="px-2 py-2 text-left">Run A · {timeAgo(a.created_at)}</th>
            <th className="px-2 py-2 text-left">Run B · {timeAgo(b.created_at)}</th>
          </tr>
          <tr className="text-[10px] text-slate-400">
            <td></td>
            <td className="px-2 py-1">best mAP {num(a.best_metric, 4)}</td>
            <td className="px-2 py-1">best mAP {num(b.best_metric, 4)}</td>
          </tr>
        </thead>
        <tbody>
          {keys.map((k) => {
            const va = a.params[k];
            const vb = b.params[k];
            const differ = JSON.stringify(va) !== JSON.stringify(vb);
            return (
              <tr key={k} className={'border-t border-slate-100 ' + (differ ? 'bg-blue-50' : '')}>
                <td className="px-2 py-1.5 font-mono text-[11px]">{k}</td>
                <td className={'px-2 py-1.5 font-mono ' + (differ ? 'font-bold text-blue-800' : '')}>
                  {String(va ?? '—')}
                </td>
                <td className={'px-2 py-1.5 font-mono ' + (differ ? 'font-bold text-blue-800' : '')}>
                  {String(vb ?? '—')}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
