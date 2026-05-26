import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
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
  const qc = useQueryClient();
  const start = useStartAnalysis(versionId);
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useJob(jobId);
  const analysis = useAnalysis(versionId);
  const trainingRec = useTrainingRecommendation(versionId);

  // Auto-refresh: when the analyze job finishes, invalidate analysis +
  // training-rec + project so the UI updates without a manual reload.
  useEffect(() => {
    if (job.data?.status === 'succeeded') {
      qc.invalidateQueries({ queryKey: ['analysis', versionId] });
      qc.invalidateQueries({ queryKey: ['training-rec', versionId] });
      qc.invalidateQueries({ queryKey: ['project', projectId] });
      qc.invalidateQueries({ queryKey: ['project-timeline', projectId] });
    }
  }, [job.data?.status, versionId, projectId, qc]);

  const a = analysis.data;
  const hasReport = !!a;

  // Pull the label-health bucket out of findings so we can render a dedicated
  // "background images" stat alongside the existing health components.
  const labelHealth = (a?.findings?.checks as Record<string, unknown> | undefined)
    ?.label_health as
      | {
          missing?: number;
          empty?: number;
          background?: number;
          background_ratio?: number;
          treat_unlabeled_as_background?: boolean;
          image_count?: number;
        }
      | undefined;
  const totalImages =
    ((a?.findings?.checks as Record<string, unknown> | undefined)?.counts as
      | { image_count?: number }
      | undefined)?.image_count ??
    labelHealth?.image_count ??
    0;

  // Split params into basic vs augmentation using the optional `groups` field.
  const grouped = useMemo(() => {
    const params = trainingRec.data?.params ?? {};
    const groups = trainingRec.data?.groups;
    const basic = (groups?.basic ?? []).filter((k) => k in params);
    const aug = (groups?.augmentation ?? []).filter((k) => k in params);
    const claimed = new Set([...basic, ...aug]);
    const other = Object.keys(params).filter((k) => !claimed.has(k));
    return { basic, aug, other, params };
  }, [trainingRec.data]);

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
              <Spinner /> <span>{job.data.message ?? 'Working...'} ({job.data.progress}%)</span>
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
                {labelHealth && (
                  <div className="mt-4 space-y-1 border-t border-slate-200 pt-3 text-[11px] text-slate-600">
                    <div className="font-semibold uppercase tracking-wider text-slate-500">
                      Label coverage
                    </div>
                    <div className="flex justify-between">
                      <span>Total images</span>
                      <span className="font-mono">{totalImages}</span>
                    </div>
                    {labelHealth.treat_unlabeled_as_background ? (
                      <div className="flex justify-between text-emerald-700">
                        <span>Background images</span>
                        <span className="font-mono">
                          {labelHealth.background ?? 0}
                          {labelHealth.background_ratio != null && totalImages > 0 && (
                            <span className="text-slate-500">
                              {' '}
                              ({(labelHealth.background_ratio * 100).toFixed(1)}%)
                            </span>
                          )}
                        </span>
                      </div>
                    ) : (
                      <>
                        <div className="flex justify-between">
                          <span>Missing labels</span>
                          <span className="font-mono">{labelHealth.missing ?? 0}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Empty labels</span>
                          <span className="font-mono">{labelHealth.empty ?? 0}</span>
                        </div>
                      </>
                    )}
                  </div>
                )}
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
            <CardHeader
              title="Suggested training parameters"
              subtitle="From the recommendation engine. You can edit any of these on the next page."
            />
            <CardBody className="space-y-4">
              {trainingRec.isLoading && <Spinner />}
              {trainingRec.data && (
                <>
                  <ParamGrid
                    title="Basic"
                    keys={grouped.basic.length ? grouped.basic : Object.keys(grouped.params)}
                    params={grouped.params}
                    reasons={trainingRec.data.reasons}
                  />
                  {grouped.aug.length > 0 && (
                    <ParamGrid
                      title="Augmentation"
                      subtitle="Tuned for your dataset size, task, and class balance."
                      keys={grouped.aug}
                      params={grouped.params}
                      reasons={trainingRec.data.reasons}
                    />
                  )}
                  {grouped.other.length > 0 && (
                    <ParamGrid
                      title="Other"
                      keys={grouped.other}
                      params={grouped.params}
                      reasons={trainingRec.data.reasons}
                    />
                  )}
                </>
              )}
              <div className="flex items-center justify-between gap-3">
                {a.ready_for_training ? (
                  <span className="text-xs text-emerald-700">Health checks pass — ready to train.</span>
                ) : (
                  <span className="text-xs text-amber-700">
                    Health checks flagged blockers — you can still configure training; you'll be
                    asked to confirm the override before starting.
                  </span>
                )}
                <Link to={`/projects/${projectId}/train?version=${versionId}`}>
                  <Button variant={a.ready_for_training ? 'primary' : 'secondary'}>
                    Configure training -&gt;
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


function ParamGrid({
  title, subtitle, keys, params, reasons,
}: {
  title: string;
  subtitle?: string;
  keys: string[];
  params: Record<string, unknown>;
  reasons: Record<string, string>;
}) {
  return (
    <section>
      <header className="mb-2">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-600">{title}</h4>
        {subtitle && <p className="text-[11px] text-slate-500">{subtitle}</p>}
      </header>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {keys.map((k) => (
          <div key={k} className="rounded-md border border-slate-200 px-3 py-2">
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-[11px] text-slate-500">{k}</span>
              <span className="font-mono text-sm text-slate-900">{String(params[k])}</span>
            </div>
            {reasons[k] && (
              <div className="mt-1 text-[11px] text-slate-500">{reasons[k]}</div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
