import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/Button';
import { Card, CardBody, CardHeader } from '../../components/Card';
import { Field, Input, Select, Textarea } from '../../components/Input';
import { PageHeader } from '../../components/PageHeader';
import { ApiError } from '../../lib/api';
import type { ModelFamily, TaskType } from '../../lib/types';
import { useCreateProject } from './api';

export function NewProjectPage() {
  const navigate = useNavigate();
  const create = useCreateProject();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [modelFamily, setModelFamily] = useState<ModelFamily>('yolo');
  const [taskType, setTaskType] = useState<TaskType>('detection');

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const p = await create.mutateAsync({
        name: name.trim(),
        description: description.trim() || undefined,
        model_family: modelFamily,
        task_type: taskType,
      });
      navigate(`/projects/${p.id}`);
    } catch {
      /* handled below via create.error */
    }
  }

  const err = create.error instanceof ApiError ? create.error.message : null;

  return (
    <div>
      <PageHeader title="New project" subtitle="A project owns datasets and training runs." />
      <form onSubmit={onSubmit}>
        <Card>
          <CardHeader title="Project details" />
          <CardBody className="space-y-4">
            <Field label="Name">
              <Input value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} />
            </Field>
            <Field label="Description (optional)">
              <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
            </Field>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Model family">
                <Select value={modelFamily} onChange={(e) => setModelFamily(e.target.value as ModelFamily)}>
                  <option value="yolo">YOLO (Ultralytics)</option>
                </Select>
              </Field>
              <Field label="Task type" hint="Detection produces bboxes; segmentation polygons; classification a single label per image.">
                <Select value={taskType} onChange={(e) => setTaskType(e.target.value as TaskType)}>
                  <option value="detection">Detection</option>
                  <option value="segmentation">Segmentation</option>
                  <option value="classification">Classification</option>
                </Select>
              </Field>
            </div>
            {err && (
              <p className="rounded bg-red-50 px-3 py-2 text-xs text-red-700">{err}</p>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="secondary" type="button" onClick={() => navigate(-1)}>Cancel</Button>
              <Button type="submit" loading={create.isPending} disabled={!name.trim()}>
                Create project
              </Button>
            </div>
          </CardBody>
        </Card>
      </form>
    </div>
  );
}
