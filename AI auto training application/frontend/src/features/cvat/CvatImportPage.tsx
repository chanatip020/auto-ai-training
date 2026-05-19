import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Button } from '../../components/Button';
import { Card, CardBody, CardHeader } from '../../components/Card';
import { Field, Select } from '../../components/Input';
import { Spinner } from '../../components/Spinner';
import { PageHeader } from '../../components/PageHeader';
import { StatusPill } from '../../components/StatusPill';
import { ApiError } from '../../lib/api';
import { timeAgo } from '../../lib/format';
import { useProject } from '../projects/api';
import {
  useCvatConnections,
  useCvatImport,
  useCvatProjects,
  useCvatTasks,
  useStartCvatImport,
} from './api';


type SourceType = 'cvat_project' | 'cvat_task';


export function CvatImportPage() {
  const { id: projectId = '' } = useParams();
  const navigate = useNavigate();
  const project = useProject(projectId);
  const connections = useCvatConnections();

  const [connectionId, setConnectionId] = useState<string | null>(null);
  const [sourceType, setSourceType] = useState<SourceType>('cvat_project');
  const [pickedProjectId, setPickedProjectId] = useState<number | null>(null);
  const [pickedTaskId, setPickedTaskId] = useState<number | null>(null);
  const [importId, setImportId] = useState<string | null>(null);

  // Auto-select first connection
  useEffect(() => {
    if (!connectionId && connections.data?.items?.[0]) {
      setConnectionId(connections.data.items[0].id);
    }
  }, [connections.data, connectionId]);

  const cvatProjects = useCvatProjects(connectionId);
  const cvatTasks = useCvatTasks(
    connectionId,
    sourceType === 'cvat_task' ? pickedProjectId : null,
  );

  const start = useStartCvatImport(projectId);
  const importStatus = useCvatImport(importId);

  // When the import finishes, refresh the dataset page so the new dataset shows.
  useEffect(() => {
    if (importStatus.data?.status === 'succeeded') {
      // Slight delay so the dataset row finishes being created downstream.
      const t = setTimeout(() => navigate(`/projects/${projectId}/dataset`), 1500);
      return () => clearTimeout(t);
    }
  }, [importStatus.data?.status, projectId, navigate]);

  const noConnections = connections.data && connections.data.total === 0;
  const startErr = start.error instanceof ApiError ? start.error.message : null;

  const sourceLabel = useMemo(() => {
    if (sourceType === 'cvat_project' && pickedProjectId != null) {
      return cvatProjects.data?.find((p) => p.id === pickedProjectId)?.name ?? '';
    }
    if (sourceType === 'cvat_task' && pickedTaskId != null) {
      return cvatTasks.data?.find((t) => t.id === pickedTaskId)?.name ?? '';
    }
    return '';
  }, [sourceType, pickedProjectId, pickedTaskId, cvatProjects.data, cvatTasks.data]);

  async function onImport() {
    if (!connectionId) return;
    const sourceId =
      sourceType === 'cvat_project' ? pickedProjectId : pickedTaskId;
    if (sourceId == null) return;
    try {
      const imp = await start.mutateAsync({
        connection_id: connectionId,
        source_type: sourceType,
        source_id: sourceId,
        source_name: sourceLabel || undefined,
      });
      setImportId(imp.id);
    } catch {/* shown via start.error */}
  }

  return (
    <div>
      <PageHeader
        title="Import from CVAT"
        subtitle={project.data ? `Project: ${project.data.name}` : ''}
      />

      {noConnections ? (
        <Card>
          <CardBody className="text-center text-sm text-slate-600">
            No CVAT connections saved yet.{' '}
            <Link to="/settings" className="text-blue-600 underline">
              Add one in Settings
            </Link>
            .
          </CardBody>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader title="Wizard" subtitle="Pick a connection, then a project or task." />
            <CardBody className="space-y-4">
              <Field label="CVAT connection">
                <Select
                  value={connectionId ?? ''}
                  onChange={(e) => setConnectionId(e.target.value || null)}
                >
                  {connections.data?.items.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} — {c.base_url}
                    </option>
                  ))}
                </Select>
              </Field>

              <Field label="Import what?">
                <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
                  <button
                    type="button"
                    onClick={() => { setSourceType('cvat_project'); setPickedTaskId(null); }}
                    className={
                      'rounded-md px-3 py-1 ' +
                      (sourceType === 'cvat_project'
                        ? 'bg-white shadow-sm font-medium text-slate-900'
                        : 'text-slate-500')
                    }
                  >
                    Entire project
                  </button>
                  <button
                    type="button"
                    onClick={() => setSourceType('cvat_task')}
                    className={
                      'rounded-md px-3 py-1 ' +
                      (sourceType === 'cvat_task'
                        ? 'bg-white shadow-sm font-medium text-slate-900'
                        : 'text-slate-500')
                    }
                  >
                    Single task
                  </button>
                </div>
              </Field>

              {sourceType === 'cvat_project' && (
                <Field label="CVAT project">
                  {cvatProjects.isLoading && <Spinner />}
                  {cvatProjects.error && (
                    <p className="text-xs text-red-700">
                      {(cvatProjects.error as ApiError).message ?? String(cvatProjects.error)}
                    </p>
                  )}
                  {cvatProjects.data && (
                    <Select
                      value={pickedProjectId ?? ''}
                      onChange={(e) => setPickedProjectId(e.target.value ? Number(e.target.value) : null)}
                    >
                      <option value="">— choose a project —</option>
                      {cvatProjects.data.map((p) => (
                        <option key={p.id} value={p.id}>
                          [{p.id}] {p.name}
                          {p.tasks_count != null ? ` · ${p.tasks_count} tasks` : ''}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              )}

              {sourceType === 'cvat_task' && (
                <>
                  <Field label="Filter by project (optional)">
                    {cvatProjects.data && (
                      <Select
                        value={pickedProjectId ?? ''}
                        onChange={(e) => setPickedProjectId(e.target.value ? Number(e.target.value) : null)}
                      >
                        <option value="">— any —</option>
                        {cvatProjects.data.map((p) => (
                          <option key={p.id} value={p.id}>
                            [{p.id}] {p.name}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                  <Field label="CVAT task">
                    {cvatTasks.isLoading && <Spinner />}
                    {cvatTasks.data && (
                      <Select
                        value={pickedTaskId ?? ''}
                        onChange={(e) => setPickedTaskId(e.target.value ? Number(e.target.value) : null)}
                      >
                        <option value="">— choose a task —</option>
                        {cvatTasks.data.map((t) => (
                          <option key={t.id} value={t.id}>
                            [{t.id}] {t.name}
                            {t.size != null ? ` · ${t.size} frames` : ''}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                </>
              )}

              {startErr && (
                <p className="rounded bg-red-50 px-3 py-2 text-xs text-red-700 whitespace-pre-line">
                  {startErr}
                </p>
              )}

              <div className="flex justify-end gap-2">
                <Link to={`/projects/${projectId}/dataset`}>
                  <Button variant="secondary">Cancel</Button>
                </Link>
                <Button
                  onClick={onImport}
                  loading={start.isPending}
                  disabled={
                    !connectionId ||
                    (sourceType === 'cvat_project' && pickedProjectId == null) ||
                    (sourceType === 'cvat_task' && pickedTaskId == null) ||
                    importStatus.data?.status === 'running'
                  }
                >
                  Start import
                </Button>
              </div>

              {importId && importStatus.data && (
                <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {(importStatus.data.status === 'running' ||
                        importStatus.data.status === 'pending') && <Spinner size={12} />}
                      <StatusPill status={importStatus.data.status} />
                      <span className="text-slate-700">
                        {importStatus.data.message ?? 'working…'}
                      </span>
                    </div>
                    <span className="font-mono text-slate-500">
                      {importStatus.data.progress}%
                    </span>
                  </div>
                  {importStatus.data.error && (
                    <p className="mt-2 whitespace-pre-line text-red-700">
                      {importStatus.data.error}
                    </p>
                  )}
                  {importStatus.data.status === 'succeeded' && (
                    <p className="mt-2 text-emerald-700">
                      Import done — taking you to datasets…
                    </p>
                  )}
                </div>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="What this does" />
            <CardBody className="space-y-2 text-xs text-slate-600">
              <p>1. Connects to your CVAT server.</p>
              <p>2. Requests an export of the selected project/task in YOLO 1.1 format.</p>
              <p>3. Streams the resulting ZIP into this project.</p>
              <p>4. Runs the same ingest pipeline as a manual ZIP upload — your new dataset version appears under <Link to={`/projects/${projectId}/dataset`} className="text-blue-600 underline">Dataset</Link>.</p>
              <p className="mt-3 text-[11px] text-slate-500">
                Tip: this uses the CVAT 2.x async-export API. The import is resumable — if the
                connection drops you can re-trigger from the same row and it'll pick up.
              </p>
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  );
}
