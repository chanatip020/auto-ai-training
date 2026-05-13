import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Button } from '../../components/Button';
import { Card, CardBody, CardHeader } from '../../components/Card';
import { Field, Input, Select } from '../../components/Input';
import { FullSpinner } from '../../components/Spinner';
import { PageHeader } from '../../components/PageHeader';
import { ApiError } from '../../lib/api';
import { useTrainingRecommendation } from '../analysis/api';
import { useDatasets, useDatasetDetail } from '../datasets/api';
import { useProject } from '../projects/api';
import { useStartTraining } from './api';

export function TrainingStartPage() {
  const { id: projectId = '' } = useParams();
  const [search] = useSearchParams();
  const versionFromQuery = search.get('version');
  const navigate = useNavigate();

  const project = useProject(projectId);
  const datasets = useDatasets(projectId);

  // Default to the first dataset, then to its newest converted version.
  const firstDataset = datasets.data?.items?.[0];
  const detail = useDatasetDetail(firstDataset?.id);

  const versions = detail.data?.versions ?? [];
  const convertedVersions = versions.filter((v) => v.format !== 'raw');
  const initialVersionId =
    versionFromQuery ?? convertedVersions[0]?.id ?? '';

  const [versionId, setVersionId] = useState<string>(initialVersionId);
  useEffect(() => {
    if (!versionId && convertedVersions[0]) setVersionId(convertedVersions[0].id);
  }, [versionId, convertedVersions]);

  const rec = useTrainingRecommendation(versionId || undefined);

  // Editable params form, seeded by the recommendation
  const [model, setModel] = useState('yolov8n');
  const [epochs, setEpochs] = useState(50);
  const [imgsz, setImgsz] = useState(640);
  const [batch, setBatch] = useState(16);
  const [lr0, setLr0] = useState(0.01);

  useEffect(() => {
    if (rec.data) {
      const p = rec.data.params as Record<string, unknown>;
      if (typeof p.model === 'string') setModel(p.model);
      if (typeof p.epochs === 'number') setEpochs(p.epochs);
      if (typeof p.imgsz === 'number') setImgsz(p.imgsz);
      if (typeof p.batch === 'number') setBatch(p.batch);
      if (typeof p.lr0 === 'number') setLr0(p.lr0);
    }
  }, [rec.data]);

  const start = useStartTraining(projectId);

  async function onStart() {
    if (!versionId) return;
    try {
      const tj = await start.mutateAsync({
        dataset_version_id: versionId,
        params: { model, epochs, imgsz, batch, lr0, device: 'cpu' },
      });
      navigate(`/projects/${projectId}/train/${tj.id}`);
    } catch {
      /* shown via start.error */
    }
  }

  const err = start.error instanceof ApiError ? start.error.message : null;

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
          <Card className="lg:col-span-2">
            <CardHeader title="Hyperparameters" subtitle="Defaults filled from the recommendation engine." />
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

              <div className="grid grid-cols-2 gap-3">
                <Field label="Model">
                  <Select value={model} onChange={(e) => setModel(e.target.value)}>
                    <option value="yolov8n">yolov8n (nano)</option>
                    <option value="yolov8s">yolov8s (small)</option>
                    <option value="yolov8m">yolov8m (medium)</option>
                  </Select>
                </Field>
                <Field label="Epochs">
                  <Input type="number" min={1} max={300} value={epochs}
                         onChange={(e) => setEpochs(parseInt(e.target.value || '50'))} />
                </Field>
                <Field label="Image size (imgsz)">
                  <Select value={imgsz} onChange={(e) => setImgsz(parseInt(e.target.value))}>
                    <option value={320}>320</option>
                    <option value={640}>640</option>
                    <option value={1280}>1280</option>
                  </Select>
                </Field>
                <Field label="Batch size">
                  <Input type="number" min={1} max={128} value={batch}
                         onChange={(e) => setBatch(parseInt(e.target.value || '16'))} />
                </Field>
                <Field label="Learning rate (lr0)">
                  <Input type="number" step="0.0001" min={0.0001} max={1} value={lr0}
                         onChange={(e) => setLr0(parseFloat(e.target.value || '0.01'))} />
                </Field>
              </div>

              {err && <p className="rounded bg-red-50 px-3 py-2 text-xs text-red-700">{err}</p>}

              <div className="flex justify-end">
                <Button onClick={onStart} loading={start.isPending} disabled={!versionId}>
                  Start training
                </Button>
              </div>
            </CardBody>
          </Card>

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
        </div>
      )}
    </div>
  );
}
