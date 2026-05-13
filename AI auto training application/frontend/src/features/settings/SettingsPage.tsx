import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/Button';
import { Card, CardBody, CardHeader } from '../../components/Card';
import { Field, Input } from '../../components/Input';
import { PageHeader } from '../../components/PageHeader';
import { clearToken, getToken } from '../../lib/auth';

export function SettingsPage() {
  const navigate = useNavigate();
  const token = getToken();
  const [revealed, setRevealed] = useState(false);

  return (
    <div>
      <PageHeader title="Settings" />

      <div className="space-y-4">
        <Card>
          <CardHeader title="API token" subtitle="v1 single-user. Used as Authorization: Bearer …" />
          <CardBody className="space-y-3">
            <Field label="Current token">
              <Input
                readOnly
                value={token ? (revealed ? token : '•'.repeat(Math.min(token.length, 32))) : '(not set)'}
              />
            </Field>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setRevealed((v) => !v)}>
                {revealed ? 'Hide' : 'Reveal'}
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  clearToken();
                  navigate('/login');
                }}
              >
                Sign out
              </Button>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="CVAT connections"
            subtitle="Coming in Phase 6 — backend integration not yet wired."
          />
          <CardBody>
            <CvatConnectionsPlaceholder />
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Storage" subtitle="v1 uses local disk. MinIO/S3 wiring is config-only later." />
          <CardBody>
            <p className="text-xs text-slate-600">
              Backend reads <code className="rounded bg-slate-100 px-1">STORAGE_BACKEND</code> from
              <code className="mx-1 rounded bg-slate-100 px-1">backend/.env</code>. Switching to
              <code className="mx-1 rounded bg-slate-100 px-1">minio</code> or
              <code className="mx-1 rounded bg-slate-100 px-1">s3</code> doesn't change any
              database rows — every <code>storage_uri</code> is opaque.
            </p>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function CvatConnectionsPlaceholder() {
  return (
    <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 p-5">
      <div className="mb-3 text-sm font-medium text-slate-700">Saved CVAT servers</div>
      <p className="mb-4 text-xs text-slate-500">
        Once Phase 6 ships, each row below will let you select an existing CVAT server,
        list its projects/tasks, and trigger an import that lands as a new dataset in
        any project. The backend already reserves <code className="font-mono">cvat_connections</code> and{' '}
        <code className="font-mono">cvat_imports</code> tables in the design doc.
      </p>

      {/* Mock UI showing the planned shape */}
      <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-3 opacity-60">
        <Field label="Name">
          <Input disabled placeholder="prod-cvat" />
        </Field>
        <Field label="Server URL">
          <Input disabled placeholder="https://cvat.example.com" />
        </Field>
        <Field label="Username / API token">
          <Input disabled placeholder="alice / cvat-api-key" />
        </Field>
      </div>
      <div className="flex justify-between">
        <span className="text-xs italic text-slate-500">No connections yet.</span>
        <Button disabled>Add connection (disabled)</Button>
      </div>
    </div>
  );
}
