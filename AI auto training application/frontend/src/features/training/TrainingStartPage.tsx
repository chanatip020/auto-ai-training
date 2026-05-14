import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Button } from '../../components/Button';
import { Card, CardBody, CardHeader } from '../../components/Card';
import { Collapsible } from '../../components/Collapsible';
import { Field, Input, Select } from '../../components/Input';
import { FullSpinner } from '../../components/Spinner';
import { PageHeader } from '../../components/PageHeader';
import { ApiError } from '../../lib/api';
import { useAnalysis, useTrainingRecommendation } from '../analysis/api';
import { useDatasets, useDatasetDetail } from '../datasets/api';
import { useProject } from '../projects/api';
import { useStartTraining } from './api';


/** Default training params keyed by Ultralytics arg names.
 * https://docs.ultralytics.com/modes/train/#train-settings
 */
type ParamMap = Record<string, number | string | boolean>;

const DEFAULTS: ParamMap = {
  // basic
  model: 'yolov8n',
  epochs: 50,
  imgsz: 640,
  batch: 16,
  device: 'cpu',

  // optimization
  optimizer: 'auto',         // SGD | Adam | AdamW | NAdam | RAdam | RMSProp | auto
  lr0: 0.01,
  lrf: 0.01,
  momentum: 0.937,
  weight_decay: 0.0005,
  warmup_epochs: 3.0,
  warmup_momentum: 0.8,
  warmup_bias_lr: 0.1,
  cos_lr: false,
  patience: 100,             // early-stop patience
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
  save_period: -1,           // -1 = only save best/last
  single_cls: false,
  rect: false,
  resume: false,
};


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

  // -------- editable params --------
  const [params, setParams] = useState<ParamMap>({ ...DEFAULTS });

  // When the recommendation comes back, patch in just the keys it suggests
  // so the user gets a smart starting point but their manual edits aren't lost.
  useEffect(() => {
    if (!rec.data) return;
    setParams((prev) => {
      const next = { ...prev };
      for (const [k, v] of Object.entries(rec.data!.params || {})) {
        if (v !== undefined && v !== null) next[k] = v as number | string | boolean;
      }
      return next;
    });
  }, [rec.data]);

  // -------- override readiness --------
  const ready = analysis.data?.ready_for_training ?? null;   // null = unknown / not analyzed yet
  const blockers = (analysis.data?.recommendations || []).filter((r) => r.severity === 'blocker');
  const [override, setOverride] = useState(false);

  const start = useStartTraining(projectId);

  async function onStart() {
    if (!versionId) return;
    if (ready === false && !override) return;
    try {
      const tj = await start.mutateAsync({
        dataset_version_id: versionId,
        params,
      });
      navigate(`/projects/${projectId}/train/${tj.id}`);
    } catch {
      /* shown via start.error */
    }
  }

  const err = start.error instanceof ApiError ? start.error.message : null;
  const cannotStart =
    !versionId || start.isPending || (ready === false && !override);

  function setNum(k: string) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setParams((p) => ({ ...p, [k]: e.target.value === '' ? '' : Number(e.target.value) }));
  }
  function setStr(k: string) {
    return (e: React.ChangeEvent<HTMLSelectElement | HTMLInputElement>) =>
      setParams((p) => ({ ...p, [k]: e.target.value }));
  }
  function setBool(k: string) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setParams((p) => ({ ...p, [k]: e.target.checked }));
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
            No converted dataset versions yet. <Link to={`/projects/${projectId}/dataset`} className="text-blue-600 underline">Upload + convert one</Link> first.
          </CardBody>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* ---------- form ---------- */}
          <div className="space-y-4 lg:col-span-2">
            <Card>
              <CardHeader title="Hyperparameters" subtitle="Defaults filled from the recommendation engine. Edit anything." />
              <CardBody className="space-y-4">
                <Field label="Dataset version">
                  <Select value={versionId} onChange={(e) => setVersionId(e.target.value)}>
                    {convertedVersions.map((v) => (
                      <option key={v.id} value={v.id}>
                        v{v.version} · {v.format} · {v.num_images ?? '?'} images
                      </option>
                    ))}
                  </Select>
                </Field>

                {/* ----- Basic ----- */}
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Model">
                    <Select value={String(params.model)} onChange={setStr('model')}>
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
                    </Select>
                  </Field>
                  <Field label="Epochs">
                    <Input type="number" min={1} max={1000}
                           value={String(params.epochs)} onChange={setNum('epochs')} />
                  </Field>
                  <Field label="Image size (imgsz)">
                    <Input type="number" min={32} max={4096} step={32}
                           value={String(params.imgsz)} onChange={setNum('imgsz')} />
                  </Field>
                  <Field label="Batch">
                    <Input type="number" min={-1} max={256}
                           value={String(params.batch)} onChange={setNum('batch')} />
                  </Field>
                  <Field label="Device" hint="cpu, 0 (single GPU), 0,1 (multi-GPU)">
                    <Input value={String(params.device)} onChange={setStr('device')} />
                  </Field>
                </div>

                {/* ----- Optimization ----- */}
                <Collapsible title="Optimizer & schedule" subtitle="Learning rate, optimizer, warmup, regularization">
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Optimizer">
                      <Select value={String(params.optimizer)} onChange={setStr('optimizer')}>
                        <option value="auto">auto</option>
                        <option value="SGD">SGD</option>
                        <option value="Adam">Adam</option>
                        <option value="AdamW">AdamW</option>
                        <option value="NAdam">NAdam</option>
                        <option value="RAdam">RAdam</option>
                        <option value="RMSProp">RMSProp</option>
                      </Select>
                    </Field>
                    <Field label="lr0 (initial LR)">
                      <Input type="number" step={0.0001} value={String(params.lr0)} onChange={setNum('lr0')} />
                    </Field>
                    <Field label="lrf (final LR factor)">
                      <Input type="number" step={0.0001} value={String(params.lrf)} onChange={setNum('lrf')} />
                    </Field>
                    <Field label="Momentum">
                      <Input type="number" step={0.001} value={String(params.momentum)} onChange={setNum('momentum')} />
                    </Field>
                    <Field label="Weight decay">
                      <Input type="number" step={0.0001} value={String(params.weight_decay)} onChange={setNum('weight_decay')} />
                    </Field>
                    <Field label="Warmup epochs">
                      <Input type="number" step={0.5} value={String(params.warmup_epochs)} onChange={setNum('warmup_epochs')} />
                    </Field>
                    <Field label="Warmup momentum">
                      <Input type="number" step={0.01} value={String(params.warmup_momentum)} onChange={setNum('warmup_momentum')} />
                    </Field>
                    <Field label="Warmup bias LR">
                      <Input type="number" step={0.01} value={String(params.warmup_bias_lr)} onChange={setNum('warmup_bias_lr')} />
                    </Field>
                    <Field label="Patience (early stop)">
                      <Input type="number" min={0} value={String(params.patience)} onChange={setNum('patience')} />
                    </Field>
                    <Field label="Close mosaic (epochs)">
                      <Input type="number" min={0} value={String(params.close_mosaic)} onChange={setNum('close_mosaic')} />
                    </Field>
                    <Field label="Dropout">
                      <Input type="number" step={0.05} min={0} max={1} value={String(params.dropout)} onChange={setNum('dropout')} />
                    </Field>
                    <Field label="Label smoothing">
                      <Input type="number" step={0.01} min={0} max={1} value={String(params.label_smoothing)} onChange={setNum('label_smoothing')} />
                    </Field>
                    <Bool label="Cosine LR schedule" checked={!!params.cos_lr} onChange={setBool('cos_lr')} />
                    <Bool label="Mixed precision (AMP)" checked={!!params.amp} onChange={setBool('amp')} />
                  </div>
                </Collapsible>

                {/* ----- Augmentation ----- */}
                <Collapsible title="Augmentation" subtitle="HSV jitter, geometric transforms, mosaic, mixup">
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="HSV-H">
                      <Input type="number" step={0.005} min={0} max={1} value={String(params.hsv_h)} onChange={setNum('hsv_h')} />
                    </Field>
                    <Field label="HSV-S">
                      <Input type="number" step={0.05} min={0} max={1} value={String(params.hsv_s)} onChange={setNum('hsv_s')} />
                    </Field>
                    <Field label="HSV-V">
                      <Input type="number" step={0.05} min={0} max={1} value={String(params.hsv_v)} onChange={setNum('hsv_v')} />
                    </Field>
                    <Field label="Degrees (rotation)">
                      <Input type="number" step={1} value={String(params.degrees)} onChange={setNum('degrees')} />
                    </Field>
                    <Field label="Translate">
                      <Input type="number" step={0.01} min={0} max={1} value={String(params.translate)} onChange={setNum('translate')} />
                    </Field>
                    <Field label="Scale">
                      <Input type="number" step={0.05} min={0} max={1} value={String(params.scale)} onChange={setNum('scale')} />
                    </Field>
                    <Field label="Shear">
                      <Input type="number" step={1} value={String(params.shear)} onChange={setNum('shear')} />
                    </Field>
                    <Field label="Perspective">
                      <Input type="number" step={0.0001} min={0} max={0.001} value={String(params.perspective)} onChange={setNum('perspective')} />
                    </Field>
                    <Field label="Flip up-down">
                      <Input type="number" step={0.05} min={0} max={1} value={String(params.flipud)} onChange={setNum('flipud')} />
                    </Field>
                    <Field label="Flip left-right">
                      <Input type="number" step={0.05} min={0} max={1} value={String(params.fliplr)} onChange={setNum('fliplr')} />
                    </Field>
                    <Field label="Mosaic">
                      <Input type="number" step={0.05} min={0} max={1} value={String(params.mosaic)} onChange={setNum('mosaic')} />
                    </Field>
                    <Field label="Mixup">
                      <Input type="number" step={0.05} min={0} max={1} value={String(params.mixup)} onChange={setNum('mixup')} />
                    </Field>
                    <Field label="Copy-paste">
                      <Input type="number" step={0.05} min={0} max={1} value={String(params.copy_paste)} onChange={setNum('copy_paste')} />
                    </Field>
                  </div>
                </Collapsible>

                {/* ----- Misc ----- */}
                <Collapsible title="Advanced" subtitle="Workers, seed, periodic checkpoints, single-class, rectangular training">
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Workers">
                      <Input type="number" min={0} value={String(params.workers)} onChange={setNum('workers')} />
                    </Field>
                    <Field label="Seed">
                      <Input type="number" value={String(params.seed)} onChange={setNum('seed')} />
                    </Field>
                    <Field label="Save period (epochs, -1=off)">
                      <Input type="number" value={String(params.save_period)} onChange={setNum('save_period')} />
                    </Field>
                    <Bool label="Single class (treat all as one)" checked={!!params.single_cls} onChange={setBool('single_cls')} />
                    <Bool label="Rectangular training" checked={!!params.rect} onChange={setBool('rect')} />
                    <Bool label="Resume from last checkpoint" checked={!!params.resume} onChange={setBool('resume')} />
                  </div>
                </Collapsible>

                {/* ----- readiness override ----- */}
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
                            const ok = confirm(
                              'Training on a dataset that failed health checks may produce a poor model. Continue anyway?',
                            );
                            setOverride(ok);
                          } else {
                            setOverride(false);
                          }
                        }}
                      />
                      <span>I understand the risk and want to train anyway.</span>
                    </label>
                  </div>
                )}

                {err && <p className="rounded bg-red-50 px-3 py-2 text-xs text-red-700">{err}</p>}

                <div className="flex justify-between gap-2">
                  <Button variant="secondary" onClick={() => setParams({ ...DEFAULTS })}>
                    Reset to defaults
                  </Button>
                  <Button onClick={onStart} loading={start.isPending} disabled={cannotStart}>
                    Start training
                  </Button>
                </div>
              </CardBody>
            </Card>
          </div>

          {/* ---------- side panel ---------- */}
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

function Bool({ label, checked, onChange }: {
  label: string;
  checked: boolean;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <label className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2">
      <input type="checkbox" checked={checked} onChange={onChange} />
      <span className="text-xs text-slate-700">{label}</span>
    </label>
  );
}
