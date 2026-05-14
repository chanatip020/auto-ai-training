import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { Button } from '../../components/Button';
import { Card, CardBody, CardHeader } from '../../components/Card';
import { Field, Input } from '../../components/Input';
import { FullSpinner, Spinner } from '../../components/Spinner';
import { PageHeader } from '../../components/PageHeader';
import { StatusPill } from '../../components/StatusPill';
import { ApiError } from '../../lib/api';
import type { TaskType } from '../../lib/types';
import { useProject } from '../projects/api';
import {
  useConvert,
  useCreateDataset,
  useDatasetDetail,
  useDatasets,
  useJob,
  useUploadZip,
} from './api';

type Tab = 'zip' | 'cvat';

export function DatasetUploadPage() {
  const { id = '' } = useParams();
  const { data: project } = useProject(id);
  const datasets = useDatasets(id);

  const [tab, setTab] = useState<Tab>('zip');
  const [datasetName, setDatasetName] = useState('dataset-1');
  const create = useCreateDataset(id);
  const [pickedDatasetId, setPickedDatasetId] = useState<string | null>(null);

  useEffect(() => {
    if (!pickedDatasetId && datasets.data?.items?.[0]) {
      setPickedDatasetId(datasets.data.items[0].id);
    }
  }, [datasets.data, pickedDatasetId]);

  const detail = useDatasetDetail(pickedDatasetId ?? undefined);

  return (
    <div>
      <PageHeader
        title="Dataset"
        subtitle={project ? `Project: ${project.name}` : ''}
        action={project && <StatusPill status={project.status} />}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardHeader title="Source" />
            <CardBody>
              <div className="mb-4 inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
                <button
                  className={'rounded-md px-3 py-1 ' + (tab === 'zip' ? 'bg-white shadow-sm' : 'text-slate-500')}
                  onClick={() => setTab('zip')}
                >
                  Upload ZIP
                </button>
                <button
                  className={'rounded-md px-3 py-1 ' + (tab === 'cvat' ? 'bg-white shadow-sm' : 'text-slate-500')}
                  onClick={() => setTab('cvat')}
                >
                  Import from CVAT
                </button>
              </div>

              {tab === 'zip' && (
                <ZipUpload
                  projectId={id}
                  datasetName={datasetName}
                  setDatasetName={setDatasetName}
                  onCreated={(d) => setPickedDatasetId(d)}
                  createPending={create.isPending}
                  createMutate={async () => (await create.mutateAsync(datasetName)).id}
                />
              )}
              {tab === 'cvat' && <CvatPlaceholder />}
            </CardBody>
          </Card>

          {pickedDatasetId && (
            <Card>
              <CardHeader title="Versions" subtitle="Latest first." />
              <CardBody>
                {detail.isLoading && <FullSpinner />}
                {detail.data && detail.data.versions.length === 0 && (
                  <p className="text-sm text-slate-500">
                    No versions yet — upload a ZIP above to create v1.
                  </p>
                )}
                {detail.data && detail.data.versions.length > 0 && (
                  <ConvertSection
                    projectId={id}
                    datasetId={pickedDatasetId}
                    taskType={(project?.task_type ?? 'detection') as TaskType}
                    versions={detail.data.versions}
                  />
                )}
              </CardBody>
            </Card>
          )}
        </div>

        <Card>
          <CardHeader title="Datasets in this project" />
          <CardBody className="space-y-2">
            {datasets.data?.items?.length ? (
              datasets.data.items.map((d) => (
                <button
                  key={d.id}
                  onClick={() => setPickedDatasetId(d.id)}
                  className={
                    'block w-full rounded-md border px-3 py-2 text-left text-sm ' +
                    (pickedDatasetId === d.id
                      ? 'border-blue-400 bg-blue-50'
                      : 'border-slate-200 hover:bg-slate-50')
                  }
                >
                  <div className="font-medium text-slate-900">{d.name}</div>
                  <div className="text-[11px] text-slate-500">
                    {d.source} · {new Date(d.created_at).toLocaleDateString()}
                  </div>
                </button>
              ))
            ) : (
              <p className="text-sm text-slate-500">No datasets yet.</p>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function ZipUpload({
  projectId,
  datasetName,
  setDatasetName,
  onCreated,
  createPending,
  createMutate,
}: {
  projectId: string;
  datasetName: string;
  setDatasetName: (v: string) => void;
  onCreated: (id: string) => void;
  createPending: boolean;
  createMutate: () => Promise<string>;
}) {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [createdDsId, setCreatedDsId] = useState<string | null>(null);
  const upload = useUploadZip();
  const job = useJob(jobId);

  // Auto-refresh the dataset detail and dataset list when the ingest job finishes.
  useEffect(() => {
    if (job.data?.status === 'succeeded' && createdDsId) {
      qc.invalidateQueries({ queryKey: ['dataset', createdDsId] });
      qc.invalidateQueries({ queryKey: ['datasets', projectId] });
      qc.invalidateQueries({ queryKey: ['project', projectId] });
      qc.invalidateQueries({ queryKey: ['project-timeline', projectId] });
    }
  }, [job.data?.status, createdDsId, projectId, qc]);

  async function start() {
    if (!file) return;
    let dsId = createdDsId;
    if (!dsId) {
      dsId = await createMutate();
      setCreatedDsId(dsId);
      onCreated(dsId);
    }
    const r = await upload.mutateAsync({ datasetId: dsId, file });
    setJobId(r.job_id);
  }

  const err = upload.error instanceof ApiError ? upload.error.message : null;

  return (
    <div className="space-y-4">
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-slate-700">Dataset name</span>
        <input
          className="block w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          value={datasetName}
          onChange={(e) => setDatasetName(e.target.value)}
        />
      </label>
      <label className="block cursor-pointer rounded-md border-2 border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center hover:border-blue-400">
        <input
          type="file"
          accept=".zip"
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        {file ? (
          <p className="text-sm font-medium text-slate-800">
            {file.name}
            <span className="ml-2 text-xs text-slate-500">
              ({(file.size / 1024).toFixed(1)} KB)
            </span>
          </p>
        ) : (
          <p className="text-sm text-slate-500">Click to choose a .zip file</p>
        )}
      </label>
      <div className="flex justify-end">
        <Button
          onClick={start}
          loading={createPending || upload.isPending}
          disabled={!file || !datasetName.trim()}
        >
          Upload + ingest
        </Button>
      </div>
      {err && <p className="rounded bg-red-50 px-3 py-2 text-xs text-red-700">{err}</p>}

      {jobId && job.data && (
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {job.data.status === 'running' || job.data.status === 'pending' ? <Spinner size={12} /> : null}
              <StatusPill status={job.data.status} />
              <span className="text-slate-700">{job.data.message ?? 'working…'}</span>
            </div>
            <span className="font-mono text-slate-500">{job.data.progress}%</span>
          </div>
          {job.data.error && <p className="mt-2 text-red-700">{job.data.error}</p>}
        </div>
      )}
    </div>
  );
}

function ConvertSection({
  projectId,
  datasetId,
  taskType,
  versions,
}: {
  projectId: string;
  datasetId: string;
  taskType: TaskType;
  versions: { id: string; version: number; format: string; num_images: number | null;
              num_classes: number | null; classes: string[] | null;
              summary: Record<string, unknown> }[];
}) {
  const qc = useQueryClient();
  const convert = useConvert();
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useJob(jobId);
  const targetFormat = useMemo(
    () => (taskType === 'detection' ? 'yolo-det' :
           taskType === 'segmentation' ? 'yolo-seg' : 'yolo-cls'),
    [taskType],
  );

  // Split ratios — editable, default 70/20/10
  const [train, setTrain] = useState(0.7);
  const [val, setVal] = useState(0.2);
  const [test, setTest] = useState(0.1);
  const sum = +(train + val + test).toFixed(3);
  const splitValid = Math.abs(sum - 1) < 0.005 && train >= 0 && val >= 0 && test >= 0;

  // Auto-refresh dataset detail when convert job succeeds
  useEffect(() => {
    if (job.data?.status === 'succeeded') {
      qc.invalidateQueries({ queryKey: ['dataset', datasetId] });
      qc.invalidateQueries({ queryKey: ['project', projectId] });
      qc.invalidateQueries({ queryKey: ['project-timeline', projectId] });
    }
  }, [job.data?.status, datasetId, projectId, qc]);

  async function start() {
    const r = await convert.mutateAsync({
      datasetId,
      body: { format: targetFormat, ratios: { train, val, test } },
    });
    setJobId(r.job_id);
  }

  const latestRaw = versions.find((v) => v.format === 'raw');
  const latestConverted = versions.find((v) => v.format !== 'raw');

  return (
    <div className="space-y-4">
      <ol className="space-y-2">
        {versions.map((v) => (
          <li
            key={v.id}
            className="flex items-center justify-between gap-3 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
          >
            <div className="flex items-center gap-3">
              <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">v{v.version}</span>
              <span className="font-medium">{v.format}</span>
              <span className="text-xs text-slate-500">
                {v.num_images ?? '—'} images · {v.num_classes ?? '—'} classes
              </span>
            </div>
            {v.format !== 'raw' && (
              <Link
                to={`/projects/${projectId}/analyze/${v.id}`}
                className="text-xs font-medium text-blue-600 hover:underline"
              >
                Analyze →
              </Link>
            )}
          </li>
        ))}
      </ol>

      {latestRaw && (
        <div className="space-y-3 rounded-md border border-slate-200 bg-slate-50 p-3">
          <div className="text-xs font-medium text-slate-700">
            Convert <span className="font-mono">v{latestRaw.version}</span> (raw) →{' '}
            <span className="font-mono">{targetFormat}</span>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <Field label="Train">
              <Input
                type="number" min={0} max={1} step={0.01}
                value={train}
                onChange={(e) => setTrain(parseFloat(e.target.value || '0'))}
              />
            </Field>
            <Field label="Val">
              <Input
                type="number" min={0} max={1} step={0.01}
                value={val}
                onChange={(e) => setVal(parseFloat(e.target.value || '0'))}
              />
            </Field>
            <Field label="Test">
              <Input
                type="number" min={0} max={1} step={0.01}
                value={test}
                onChange={(e) => setTest(parseFloat(e.target.value || '0'))}
              />
            </Field>
          </div>
          <div className={'text-[11px] ' + (splitValid ? 'text-slate-500' : 'text-red-600')}>
            Sum: {sum.toFixed(3)}{splitValid ? ' ✓' : ' — must equal 1.000'}
          </div>

          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => { setTrain(0.7); setVal(0.2); setTest(0.1); }}
            >
              Reset 70/20/10
            </Button>
            <Button
              onClick={start}
              disabled={!splitValid || convert.isPending}
              loading={convert.isPending || job.data?.status === 'running'}
            >
              Convert
            </Button>
          </div>
        </div>
      )}

      {jobId && job.data && (
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {(job.data.status === 'running' || job.data.status === 'pending') && <Spinner size={12} />}
              <StatusPill status={job.data.status} />
              <span className="text-slate-700">{job.data.message ?? '…'}</span>
            </div>
            <span className="font-mono text-slate-500">{job.data.progress}%</span>
          </div>
          {job.data.error && <p className="mt-2 text-red-700">{job.data.error}</p>}
        </div>
      )}

      {latestConverted && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          Latest converted: v{latestConverted.version} ({latestConverted.format}) — ready to{' '}
          <Link to={`/projects/${projectId}/analyze/${latestConverted.id}`} className="font-medium underline">
            analyze
          </Link>
          .
        </div>
      )}
    </div>
  );
}

function CvatPlaceholder() {
  return (
    <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
      <div className="mb-1 text-sm font-medium text-slate-700">Import from CVAT</div>
      <p className="mx-auto max-w-md text-xs text-slate-500">
        Coming in <strong>Phase 6</strong>. The wizard will let you connect to a CVAT server,
        pick a project or task, and import its annotations as a YOLO dataset in one step.
        Connection settings live in <Link to="/settings" className="text-blue-600 hover:underline">Settings</Link>.
      </p>
      <Button variant="secondary" disabled className="mt-4">Connect CVAT (disabled)</Button>
    </div>
  );
}
