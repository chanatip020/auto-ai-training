import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '../../components/Button';
import { Card, CardBody, CardHeader } from '../../components/Card';
import { MetricsChart } from '../../components/MetricsChart';
import { FullSpinner } from '../../components/Spinner';
import { PageHeader } from '../../components/PageHeader';
import { StatusPill } from '../../components/StatusPill';
import { formatBytes, num, timeAgo } from '../../lib/format';
import { useSSE, type SSEEvent } from '../../lib/sse';
import type { TrainingMetric } from '../../lib/types';
import {
  artifactDownloadUrl,
  sseTrainingPath,
  useArtifacts,
  useStopTraining,
  useTrainingJob,
  useTrainingMetrics,
} from './api';

export function TrainingMonitorPage() {
  const { jobId = '' } = useParams();
  const job = useTrainingJob(jobId);
  const metricsQuery = useTrainingMetrics(jobId);
  const artifacts = useArtifacts(jobId);
  const stop = useStopTraining(jobId);

  // Live metrics buffer fed from SSE.
  const [liveMetrics, setLiveMetrics] = useState<TrainingMetric[]>([]);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [logLines, setLogLines] = useState<string[]>([]);

  // Re-seed buffer from server-side history when it loads.
  useEffect(() => {
    if (metricsQuery.data) setLiveMetrics(metricsQuery.data.items);
  }, [metricsQuery.data]);

  // SSE stream — only subscribe while job is pending/running.
  const ssePath = useMemo(() => {
    if (!jobId) return null;
    if (job.data && (job.data.status === 'succeeded' || job.data.status === 'failed' || job.data.status === 'cancelled')) {
      return null;
    }
    return sseTrainingPath(jobId);
  }, [jobId, job.data?.status]);

  useSSE(ssePath, (ev: SSEEvent) => {
    if (ev.type === 'metric' && typeof ev.epoch === 'number') {
      const m: TrainingMetric = {
        epoch: ev.epoch as number,
        loss: (ev.loss as number) ?? null,
        val_loss: (ev.val_loss as number) ?? null,
        precision: (ev.precision as number) ?? null,
        recall: (ev.recall as number) ?? null,
        map50: (ev.map50 as number) ?? null,
        map5095: (ev.map5095 as number) ?? null,
        extra: {},
        recorded_at: new Date().toISOString(),
      };
      setLiveMetrics((prev) => {
        // Replace if same epoch already present, else append.
        const idx = prev.findIndex((x) => x.epoch === m.epoch);
        if (idx === -1) return [...prev, m];
        const cp = [...prev];
        cp[idx] = m;
        return cp;
      });
      setLogLines((prev) => [...prev.slice(-49),
        `epoch ${m.epoch}: loss=${num(m.loss, 3)}  map50=${num(m.map50, 3)}  map5095=${num(m.map5095, 3)}`]);
    } else if (ev.type === 'status' || ev.type === 'done' || ev.type === 'failed' || ev.type === 'cancelled') {
      setStatusMsg((ev.message as string) || ev.type);
      setLogLines((prev) => [...prev.slice(-49), `[${ev.type}] ${(ev.message as string) || ''}`]);
      // Refresh data once stream signals end-of-life.
      if (ev.type !== 'status') {
        job.refetch();
        artifacts.refetch();
        metricsQuery.refetch();
      }
    }
  });

  if (job.isLoading) return <FullSpinner label="Loading training job" />;
  if (!job.data) return <div className="text-sm text-red-700">Training job not found.</div>;

  const tj = job.data;
  const live = tj.status === 'pending' || tj.status === 'running';

  return (
    <div>
      <PageHeader
        title="Training run"
        subtitle={`Job ${tj.id.slice(0, 8)}…`}
        action={
          <>
            <StatusPill status={tj.status} />
            {live && (
              <Button
                variant="danger"
                onClick={() => stop.mutateAsync().then(() => job.refetch())}
                loading={stop.isPending}
              >
                Stop
              </Button>
            )}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Status" />
          <CardBody className="space-y-2 text-xs text-slate-600">
            <Row label="Progress" value={`${tj.progress}%`} />
            <Row label="Epoch" value={`${tj.current_epoch ?? 0} / ${tj.total_epochs ?? '?'}`} />
            <Row label="Best metric" value={num(tj.best_metric, 4)} />
            <Row label="Started" value={tj.started_at ? timeAgo(tj.started_at) : '—'} />
            <Row label="Finished" value={tj.finished_at ? timeAgo(tj.finished_at) : '—'} />
            <Row label="Message" value={statusMsg ?? tj.message ?? ''} />
            {tj.error && <p className="mt-2 text-red-700">{tj.error}</p>}
          </CardBody>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title="Loss" />
          <CardBody><MetricsChart metrics={liveMetrics} show="loss" /></CardBody>
        </Card>
        <Card className="lg:col-span-3">
          <CardHeader title="mAP" />
          <CardBody><MetricsChart metrics={liveMetrics} show="map" /></CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Live log" subtitle="Last 50 events." />
          <CardBody>
            <pre className="max-h-64 overflow-auto rounded bg-slate-900 p-3 font-mono text-[11px] leading-5 text-slate-100">
              {logLines.length === 0 ? '(idle)' : logLines.join('\n')}
            </pre>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Artifacts" />
          <CardBody>
            {artifacts.data?.items?.length ? (
              <ul className="space-y-1.5 text-xs">
                {artifacts.data.items.map((a) => (
                  <li key={a.id} className="flex items-center justify-between gap-2 rounded border border-slate-200 px-2 py-1.5">
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-mono">{a.name}</div>
                      <div className="text-[10px] text-slate-500">{a.kind} · {formatBytes(a.size_bytes)}</div>
                    </div>
                    <a
                      className="rounded bg-blue-600 px-2 py-1 text-[10px] font-medium text-white hover:bg-blue-700"
                      href={artifactDownloadUrl(jobId, a.id)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Download
                    </a>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-500">No artifacts yet — they appear when training completes.</p>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-slate-500">{label}</span>
      <span className="truncate font-mono text-slate-900">{value}</span>
    </div>
  );
}
