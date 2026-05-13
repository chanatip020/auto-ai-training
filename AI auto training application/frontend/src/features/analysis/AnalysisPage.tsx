import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Button } from '../../components/Button';
import { Card, CardBody, CardHeader } from '../../components/Card';
import { HealthGauge } from '../../components/HealthGauge';
import { Spinner } from '../../components/Spinner';
import { PageHeader } from '../../components/PageHeader';
import { useJob } from '../datasets/api';
import { useAnalysis, useStartAnalysis, useTrainingRecommendation } from './api';

export function AnalysisPage() {
  const { id: projectId = '', versionId = '' } = useParams();
  const start = useStartAnalysis(versionId);
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useJob(jobId);
  const analysis = useAnalysis(versionId);
  const trainingRec = useTrainingRecommendation(versionId);

  // After a successful analyze job, refetch the analysis row.
  if (jobId && job.data?.status === 'succeeded' && analysis.dataUpdatedAt < (job.data.finished_at ? +new Date(job.data.finished_at) : 0)) {
    analysis.refetch();
  }

  const a = analysis.data;
  const hasReport = !!a;

  return (
    <div>
      <PageHeader
        title="Dataset analysis"
        subtitle="Health checks + recommendations + training-parameter suggestions."
        action={
          <Button
            onClick={async () => setJobId((await start.mutateAsync()).job_id)}
            loading={start.isPending || job.data?.status === 'running'}
          >
            {hasReport ? 'Re-run analysis' : 'Run analysis'}
          </Button>
        }
      />

      {jobId && job.data && job.data.status !== 'succeeded' && (
        <Card className="mb-4">
          <CardBody>
            <div className="flex items-center gap-3 text-sm">
              <Spinner /> <span>{job.data.message ?? 'Working…'} ({job.data.progress}%)</span>
            </div>
          </CardBody>
        </Card>
      )}

      {!hasReport && !jobId && (
        <Card>
          <CardBody className="text-center text-sm text-slate-600">
            No analysis on this version yet. Click <strong>Run analysis</strong>.
          </CardBody>
        </Card>
      )}

      {hasReport && a && (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader title="Health" />
              <CardBody>
                <HealthGauge score={a.health_score == null ? null : Number(a.health_score)} />
                <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                  {Object.entries(a.findings.components ?? {}).map(([k, v]) => (
                    <div key={k} className="flex justify-between rounded bg-slate-50 px-2 py-1">
                      <span className="text-slate-500">{k.replace('_', ' ')}</span>
                      <span className="font-mono">{Number(v).toFixed(1)}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-4 text-xs">
                  Ready for training:{' '}
                  <strong className={a.ready_for_training ? 'text-emerald-700' : 'text-amber-700'}>
                    {a.ready_for_training ? 'YES' : 'NO'}
                  </strong>
                </div>
              </CardBody>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader title="Recommendations" subtitle={`${a.recommendations.length} item(s)`} />
              <CardBody>
                {a.recommendations.length === 0 ? (
                  <p className="text-sm text-slate-500">No issues detected.</p>
                ) : (
                  <ul className="space-y-2">
                    {a.recommendations.map((r) => (
                      <li key={r.code} className="rounded-md border border-slate-200 px-3 py-2 text-xs">
                        <div className="flex items-center gap-2">
                          <span
                            className={
                              'rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ' +
                              (r.severity === 'blocker'
                                ? 'bg-red-100 text-red-700'
                                : r.severity === 'warning'
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-slate-100 text-slate-700')
                            }
                          >
                            {r.severity}
                          </span>
                          <span className="font-mono text-slate-500">{r.code}</span>
                        </div>
                        <div className="mt-1 text-slate-800">{r.message}</div>
                        {r.fix && <div className="mt-1 text-slate-500">Fix: {r.fix}</div>}
                      </li>
                    ))}
                  </ul>
                )}
              </CardBody>
            </Card>
          </div>

          <Card className="mt-4">
            <CardHeader title="Suggested training parameters" subtitle="From the recommendation engine." />
            <CardBody>
              {trainingRec.isLoading && <Spinner />}
              {trainingRec.data && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {Object.entries(trainingRec.data.params).map(([k, v]) => (
                    <div key={k} className="rounded-md border border-slate-200 px-3 py-2">
                      <div className="text-xs uppercase tracking-wider text-slate-500">{k}</div>
                      <div className="mt-1 font-mono text-sm text-slate-900">{String(v)}</div>
                      {trainingRec.data.reasons[k] && (
                        <div className="mt-1 text-[11px] text-slate-500">{trainingRec.data.reasons[k]}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
              <div className="mt-4 flex justify-end">
                <Link to={`/projects/${projectId}/train?version=${versionId}`}>
                  <Button disabled={!a.ready_for_training} title={a.ready_for_training ? '' : 'Resolve blockers first'}>
                    Configure training →
                  </Button>
                </Link>
              </div>
            </CardBody>
          </Card>
        </>
      )}
    </div>
  );
}
