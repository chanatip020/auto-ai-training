import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Button } from '../../components/Button';
import { Card, CardBody, CardHeader } from '../../components/Card';
import { Collapsible } from '../../components/Collapsible';
import { FullSpinner } from '../../components/Spinner';
import { PageHeader } from '../../components/PageHeader';
import { ApiError } from '../../lib/api';
import { useAnalysis, useTrainingRecommendation } from '../analysis/api';
import { useDatasets, useDatasetDetail } from '../datasets/api';
import { useProject } from '../projects/api';
import { useStartTraining } from './api';


type ParamVal = number | string | boolean;
type ParamMap = Record<string, ParamVal>;

/**
 * Canonical Ultralytics YOLO defaults.
 * Source: https://docs.ultralytics.com/modes/train/#train-settings
 * Used as the "YOLO defaults" preset and as the baseline for the diff highlight.
 */
const YOLO_DEFAULTS: ParamMap = {
  // basic
  model: 'yolov8n',
  epochs: 100,
  imgsz: 640,
  batch: 16,
  device: 'cpu',

  // optimization
  optimizer: 'auto',
  lr0: 0.01,
  lrf: 0.01,
  momentum: 0.937,
  weight_decay: 0.0005,
  warmup_epochs: 3.0,
  warmup_momentum: 0.8,
  warmup_bias_lr: 0.1,
  cos_lr: false,
  patience: 100,
  close_mosaic: 10,
  amp: true,
  dropout: 0.0,
  label_smoothing: 0.0,

  // augmentation
  hsv_h: 0.015,
  hsv_s: 0.7,
  hsv_v: 0.4,
  degrees: 0.0,
  translate: 0.1,
  scale: 0.5,
  shear: 0.0,
  perspective: 0.0,
  flipud: 0.0,
  fliplr: 0.5,
  mosaic: 1.0,
  mixup: 0.0,
  copy_paste: 0.0,

  // misc
  workers: 8,
  seed: 0,
  save_period: -1,
  single_cls: false,
  rect: false,
  resume: false,
};


function equalParam(a: ParamVal | undefined, b: ParamVal | undefined): boolean {
  if (a === undefined || b === undefined) return a === b;
  // numeric tolerance for floats produced by the rec engine
  if (typeof a === 'number' && typeof b === 'number') {
    return Math.abs(a - b) < 1e-6;
  }
  return a === b;
}


export function TrainingStartPage() {
  const { id: projectId = '' } = useParams();
  const [search] = useSearchParams();
  const versionFromQuery = search.get('version');
  const navigate = useNavigate();

  const project = useProject(projectId);
  const datasets = useDatasets(projectId);
  const firstDataset = datasets.data?.items?.[0];
  const detail = useDatasetDetail(firstDataset?.id);

  const versions = detail.data?.versions ?? [];
  const convertedVersions = versions.filter((v) => v.format !== 'raw');
  const initialVersionId = versionFromQuery ?? convertedVersions[0]?.id ?? '';

  const [versionId, setVersionId] = useState<string>(initialVersionId);
  useEffect(() => {
    if (!versionId && convertedVersions[0]) setVersionId(convertedVersions[0].id);
  }, [versionId, convertedVersions]);

  const rec = useTrainingRecommendation(versionId || undefined);
  const analysis = useAnalysis(versionId || undefined);

  // --- params + preset selector ----
  const [params, setParams] = useState<ParamMap>({ ...YOLO_DEFAULTS });
  const [preset, setPreset] = useState<'recommended' | 'default'>('recommended');

  // Compute the "recommended" map = defaults + rec.params (rec values win).
  const recommendedMap: ParamMap | null = useMemo(() => {
    if (!rec.data) return null;
    const m: ParamMap = { ...YOLO_DEFAULTS };
    for (const [k, v] of Object.entries(rec.data.params)) {
      if (typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean') {
        m[k] = v;
      }
    }
    return m;
  }, [rec.data]);

  // Apply preset whenever it changes or when the recommendation arrives.
  useEffect(() => {
    if (preset === 'default') {
      setParams({ ...YOLO_DEFAULTS });
    } else if (preset === 'recommended' && recommendedMap) {
      setParams({ ...recommendedMap });
    }
  }, [preset, recommendedMap]);

  // --- readiness override ---
  const ready = analysis.data?.ready_for_training ?? null;
  const blockers = (analysis.data?.recommendations || []).filter((r) => r.severity === 'blocker');
  const [override, setOverride] = useState(false);

  const start = useStartTraining(projectId);

  async function onStart() {
    if (!versionId) return;
    if (ready === false && !override) return;
    // Compute the effective preset source so the backend can record provenance:
    //   - 'recommended' if the params match the recommendation map exactly
    //   - 'default'     if they match YOLO_DEFAULTS exactly
    //   - 'manual'      if the user edited anything
    const matchesRec = recommendedMap && deepEqualParams(params, recommendedMap);
    const matchesDefault = deepEqualParams(params, YOLO_DEFAULTS);
    const effectivePresetSource: 'recommended' | 'default' | 'manual' =
      matchesRec ? 'recommended' : matchesDefault ? 'default' : 'manual';
    try {
      const tj = await start.mutateAsync({
        dataset_version_id: versionId,
        params,
        preset_source: effectivePresetSource,
        override_blockers: override,
        recommendation_snapshot: rec.data
          ? { params: rec.data.params, reasons: rec.data.reasons,
              assumptions: rec.data.assumptions } as Record<string, unknown>
          : null,
      });
      navigate(`/projects/${projectId}/train/${tj.id}`);
    } catch { /* shown via start.error */ }
  }

  function deepEqualParams(x: ParamMap, y: ParamMap): boolean {
    const keys = new Set([...Object.keys(x), ...Object.keys(y)]);
    for (const k of keys) {
      if (!equalParam(x[k], y[k])) return false;
    }
    return true;
  }

  const err = start.error instanceof ApiError ? start.error.message : null;
  const cannotStart = !versionId || start.isPending || (ready === false && !override);

  // Helper: was this key tuned by the recommendation?  (i.e. its recommended
  // value differs from the canonical YOLO default)
  function isTunedByRec(k: string): boolean {
    if (!recommendedMap) return false;
    return !equalParam(recommendedMap[k], YOLO_DEFAULTS[k]);
  }
  // Is the CURRENT value different from the YOLO baseline?  Drives the
  // blue highlight in the UI.
  function differs(k: string): boolean {
    return !equalParam(params[k], YOLO_DEFAULTS[k]);
  }

  function set(k: string, v: ParamVal) {
    setParams((p) => ({ ...p, [k]: v }));
  }

  return (
    <div>
      <PageHeader
        title="Configure training"
        subtitle={project.data ? `Project: ${project.data.name}` : ''}
      />

      {datasets.isLoading || detail.isLoading ? (
        <FullSpinner label="Loading datasets" />
      ) : convertedVersions.length === 0 ? (
        <Card>
          <CardBody className="text-center text-sm text-slate-600">
            No converted dataset versions yet.{' '}
            <Link to={`/projects/${projectId}/dataset`} className="text-blue-600 underline">
              Upload + convert one
            </Link>{' '}
            first.
          </CardBody>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <Card>
              <CardHeader title="Hyperparameters" subtitle="Pick a preset, then edit anything." />
              <CardBody className="space-y-4">

                {/* ---- preset selector ---- */}
                <div className="space-y-2">
                  <div className="text-xs font-medium text-slate-700">Parameter source</div>
                  <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
                    <button
                      type="button"
                      onClick={() => setPreset('recommended')}
                      disabled={!recommendedMap}
                      className={
                        'rounded-md px-3 py-1 ' +
                        (preset === 'recommended'
                          ? 'bg-white shadow-sm font-medium text-slate-900'
                          : 'text-slate-500 hover:text-slate-700') +
                        (recommendedMap ? '' : ' opacity-50 cursor-not-allowed')
                      }
                    >
                      Recommended {recommendedMap ? '' : '(run analysis first)'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setPreset('default')}
                      className={
                        'rounded-md px-3 py-1 ' +
                        (preset === 'default'
                          ? 'bg-white shadow-sm font-medium text-slate-900'
                          : 'text-slate-500 hover:text-slate-700')
                      }
                    >
                      YOLO defaults
                    </button>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    <span className="mr-1 inline-block h-2 w-2 rounded-sm bg-blue-500 align-middle" />
                    Blue-ringed inputs differ from the Ultralytics defaults.
                  </p>
                </div>

                <Param label="Dataset version">
                  <select
                    value={versionId}
                    onChange={(e) => setVersionId(e.target.value)}
                    className={baseInput}
                  >
                    {convertedVersions.map((v) => (
                      <option key={v.id} value={v.id}>
                        v{v.version} · {v.format} · {v.num_images ?? '?'} images
                      </option>
                    ))}
                  </select>
                </Param>

                {/* ---- Basic ---- */}
                <SectionGrid>
                  <Param label="Model" tuned={isTunedByRec('model')} highlight={differs('model')}>
                    <select value={String(params.model)} onChange={(e) => set('model', e.target.value)} className={baseInput}>
                      <option value="yolov8n">yolov8n (nano)</option>
                      <option value="yolov8s">yolov8s (small)</option>
                      <option value="yolov8m">yolov8m (medium)</option>
                      <option value="yolov8l">yolov8l (large)</option>
                      <option value="yolov8x">yolov8x (xlarge)</option>
                      <option value="yolov8n-seg">yolov8n-seg</option>
                      <option value="yolov8s-seg">yolov8s-seg</option>
                      <option value="yolov8n-cls">yolov8n-cls</option>
                      <option value="yolov8s-cls">yolov8s-cls</option>
                      <option value="yolo11n">yolo11n</option>
                      <option value="yolo11s">yolo11s</option>
                      <option value="yolo11m">yolo11m</option>
                    </select>
                  </Param>
                  <NumParam k="epochs"  params={params} set={set} highlight={differs('epochs')}  tuned={isTunedByRec('epochs')}  min={1} max={1000} />
                  <NumParam k="imgsz"   params={params} set={set} highlight={differs('imgsz')}   tuned={isTunedByRec('imgsz')}   min={32} max={4096} step={32} />
                  <NumParam k="batch"   params={params} set={set} highlight={differs('batch')}   tuned={isTunedByRec('batch')}   min={-1} max={256} />
                  <Param label="Device" tuned={isTunedByRec('device')} highlight={differs('device')} hint="cpu, 0, 0,1">
                    <input value={String(params.device)} onChange={(e) => set('device', e.target.value)} className={baseInput} />
                  </Param>
                </SectionGrid>

                <Collapsible title="Optimizer & schedule" defaultOpen>
                  <SectionGrid>
                    <Param label="optimizer" tuned={isTunedByRec('optimizer')} highlight={differs('optimizer')}>
                      <select value={String(params.optimizer)} onChange={(e) => set('optimizer', e.target.value)} className={baseInput}>
                        <option value="auto">auto</option>
                        <option value="SGD">SGD</option>
                        <option value="Adam">Adam</option>
                        <option value="AdamW">AdamW</option>
                        <option value="NAdam">NAdam</option>
                        <option value="RAdam">RAdam</option>
                        <option value="RMSProp">RMSProp</option>
                      </select>
                    </Param>
                    <NumParam k="lr0"             params={params} set={set} highlight={differs('lr0')}             tuned={isTunedByRec('lr0')}             step={0.0001} />
                    <NumParam k="lrf"             params={params} set={set} highlight={differs('lrf')}             tuned={isTunedByRec('lrf')}             step={0.0001} />
                    <NumParam k="momentum"        params={params} set={set} highlight={differs('momentum')}        tuned={isTunedByRec('momentum')}        step={0.001} />
                    <NumParam k="weight_decay"    params={params} set={set} highlight={differs('weight_decay')}    tuned={isTunedByRec('weight_decay')}    step={0.0001} />
                    <NumParam k="warmup_epochs"   params={params} set={set} highlight={differs('warmup_epochs')}   tuned={isTunedByRec('warmup_epochs')}   step={0.5} />
                    <NumParam k="warmup_momentum" params={params} set={set} highlight={differs('warmup_momentum')} tuned={isTunedByRec('warmup_momentum')} step={0.01} />
                    <NumParam k="warmup_bias_lr"  params={params} set={set} highlight={differs('warmup_bias_lr')}  tuned={isTunedByRec('warmup_bias_lr')}  step={0.01} />
                    <NumParam k="patience"        params={params} set={set} highlight={differs('patience')}        tuned={isTunedByRec('patience')}        min={0} />
                    <NumParam k="close_mosaic"    params={params} set={set} highlight={differs('close_mosaic')}    tuned={isTunedByRec('close_mosaic')}    min={0} />
                    <NumParam k="dropout"         params={params} set={set} highlight={differs('dropout')}         tuned={isTunedByRec('dropout')}         step={0.05} min={0} max={1} />
                    <NumParam k="label_smoothing" params={params} set={set} highlight={differs('label_smoothing')} tuned={isTunedByRec('label_smoothing')} step={0.01} min={0} max={1} />
                    <BoolParam k="cos_lr"         params={params} set={set} highlight={differs('cos_lr')}          tuned={isTunedByRec('cos_lr')} label="Cosine LR schedule" />
                    <BoolParam k="amp"            params={params} set={set} highlight={differs('amp')}             tuned={isTunedByRec('amp')}    label="Mixed precision (AMP)" />
                  </SectionGrid>
                </Collapsible>

                <Collapsible title="Augmentation" defaultOpen>
                  <SectionGrid>
                    <NumParam k="hsv_h"      params={params} set={set} highlight={differs('hsv_h')}      tuned={isTunedByRec('hsv_h')}      step={0.005} min={0} max={1} />
                    <NumParam k="hsv_s"      params={params} set={set} highlight={differs('hsv_s')}      tuned={isTunedByRec('hsv_s')}      step={0.05}  min={0} max={1} />
                    <NumParam k="hsv_v"      params={params} set={set} highlight={differs('hsv_v')}      tuned={isTunedByRec('hsv_v')}      step={0.05}  min={0} max={1} />
                    <NumParam k="degrees"    params={params} set={set} highlight={differs('degrees')}    tuned={isTunedByRec('degrees')}    step={1} />
                    <NumParam k="translate"  params={params} set={set} highlight={differs('translate')}  tuned={isTunedByRec('translate')}  step={0.01} min={0} max={1} />
                    <NumParam k="scale"      params={params} set={set} highlight={differs('scale')}      tuned={isTunedByRec('scale')}      step={0.05} min={0} max={1} />
                    <NumParam k="shear"      params={params} set={set} highlight={differs('shear')}      tuned={isTunedByRec('shear')}      step={1} />
                    <NumParam k="perspective" params={params} set={set} highlight={differs('perspective')} tuned={isTunedByRec('perspective')} step={0.0001} min={0} max={0.001} />
                    <NumParam k="flipud"     params={params} set={set} highlight={differs('flipud')}     tuned={isTunedByRec('flipud')}     step={0.05} min={0} max={1} />
                    <NumParam k="fliplr"     params={params} set={set} highlight={differs('fliplr')}     tuned={isTunedByRec('fliplr')}     step={0.05} min={0} max={1} />
                    <NumParam k="mosaic"     params={params} set={set} highlight={differs('mosaic')}     tuned={isTunedByRec('mosaic')}     step={0.05} min={0} max={1} />
                    <NumParam k="mixup"      params={params} set={set} highlight={differs('mixup')}      tuned={isTunedByRec('mixup')}      step={0.05} min={0} max={1} />
                    <NumParam k="copy_paste" params={params} set={set} highlight={differs('copy_paste')} tuned={isTunedByRec('copy_paste')} step={0.05} min={0} max={1} />
                  </SectionGrid>
                </Collapsible>

                <Collapsible title="Advanced">
                  <SectionGrid>
                    <NumParam k="workers"     params={params} set={set} highlight={differs('workers')}     tuned={isTunedByRec('workers')}     min={0} />
                    <NumParam k="seed"        params={params} set={set} highlight={differs('seed')}        tuned={isTunedByRec('seed')} />
                    <NumParam k="save_period" params={params} set={set} highlight={differs('save_period')} tuned={isTunedByRec('save_period')} />
                    <BoolParam k="single_cls" params={params} set={set} highlight={differs('single_cls')} tuned={isTunedByRec('single_cls')} label="Single class" />
                    <BoolParam k="rect"       params={params} set={set} highlight={differs('rect')}       tuned={isTunedByRec('rect')}       label="Rectangular training" />
                    <BoolParam k="resume"     params={params} set={set} highlight={differs('resume')}     tuned={isTunedByRec('resume')}     label="Resume last checkpoint" />
                  </SectionGrid>
                </Collapsible>

                {/* ---- readiness override ---- */}
                {ready === false && (
                  <div className="space-y-2 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-xs text-amber-900">
                    <div className="font-medium">Dataset isn't ready for training.</div>
                    <ul className="list-disc space-y-0.5 pl-5">
                      {blockers.map((b) => (
                        <li key={b.code}><span className="font-mono">{b.code}</span> — {b.message}</li>
                      ))}
                    </ul>
                    <label className="mt-2 inline-flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={override}
                        onChange={(e) => {
                          if (e.target.checked) {
                            const ok = confirm('Training on a dataset that failed health checks may produce a poor model. Continue anyway?');
                            setOverride(ok);
                          } else setOverride(false);
                        }}
                      />
                      <span>I understand the risk and want to train anyway.</span>
                    </label>
                  </div>
                )}

                {err && <p className="rounded bg-red-50 px-3 py-2 text-xs text-red-700">{err}</p>}

                <div className="flex justify-between gap-2">
                  <Button variant="secondary" onClick={() => setPreset('default')}>
                    Reset to defaults
                  </Button>
                  <Button onClick={onStart} loading={start.isPending} disabled={cannotStart}>
                    Start training
                  </Button>
                </div>
              </CardBody>
            </Card>
          </div>

          {/* side panel */}
          <div className="space-y-4">
            <Card>
              <CardHeader title="Why these defaults?" />
              <CardBody className="space-y-2 text-xs text-slate-600">
                {rec.data ? (
                  Object.entries(rec.data.reasons).map(([k, v]) => (
                    <div key={k}>
                      <div className="font-mono text-[11px] text-slate-500">{k}</div>
                      <div className="text-slate-800">{v}</div>
                    </div>
                  ))
                ) : (
                  <p>Run analysis on the dataset version to populate this panel.</p>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Live params (preview)" subtitle="What gets POST'd to the API." />
              <CardBody>
                <pre className="max-h-96 overflow-auto rounded bg-slate-900 p-2 font-mono text-[11px] leading-5 text-slate-100">
                  {JSON.stringify(params, null, 2)}
                </pre>
              </CardBody>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}


// ----- small reusable bits -----
const baseInput =
  'block w-full rounded-md border bg-white px-3 py-1.5 text-sm shadow-sm ' +
  'placeholder:text-slate-400 focus:outline-none focus:ring-1 ' +
  'disabled:bg-slate-50 disabled:text-slate-500 ' +
  'border-slate-300 focus:border-blue-500 focus:ring-blue-500';
const baseInputHL =
  'block w-full rounded-md border bg-blue-50 px-3 py-1.5 text-sm shadow-sm ' +
  'placeholder:text-slate-400 focus:outline-none focus:ring-1 ' +
  'border-blue-400 ring-1 ring-blue-200 focus:border-blue-600 focus:ring-blue-500';


function SectionGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">{children}</div>;
}

function Param({
  label, hint, tuned, highlight, children,
}: {
  label: string;
  hint?: string;
  tuned?: boolean;
  highlight?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 flex items-center justify-between gap-2 text-xs font-medium text-slate-700">
        <span className={highlight ? 'text-blue-700' : ''}>{label}</span>
        {tuned && (
          <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-blue-700">
            tuned
          </span>
        )}
      </span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-slate-500">{hint}</span>}
    </label>
  );
}

function NumParam({
  k, params, set, highlight, tuned, ...rest
}: {
  k: string;
  params: ParamMap;
  set: (k: string, v: ParamVal) => void;
  highlight?: boolean;
  tuned?: boolean;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <Param label={k} tuned={tuned} highlight={highlight}>
      <input
        type="number"
        value={String(params[k] ?? '')}
        onChange={(e) => set(k, e.target.value === '' ? '' as unknown as number : Number(e.target.value))}
        className={highlight ? baseInputHL : baseInput}
        {...rest}
      />
    </Param>
  );
}

function BoolParam({
  k, params, set, highlight, tuned, label,
}: {
  k: string;
  params: ParamMap;
  set: (k: string, v: ParamVal) => void;
  highlight?: boolean;
  tuned?: boolean;
  label: string;
}) {
  return (
    <Param label={label} tuned={tuned} highlight={highlight}>
      <div className={
        'flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm ' +
        (highlight
          ? 'border-blue-400 bg-blue-50 ring-1 ring-blue-200'
          : 'border-slate-300 bg-white')
      }>
        <input
          type="checkbox"
          checked={!!params[k]}
          onChange={(e) => set(k, e.target.checked)}
        />
        <span className="font-mono text-[11px] text-slate-600">{k}</span>
      </div>
    </Param>
  );
}
