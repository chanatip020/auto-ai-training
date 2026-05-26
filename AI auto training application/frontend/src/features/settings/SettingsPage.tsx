import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/Button';
import { Card, CardBody, CardHeader } from '../../components/Card';
import { Field, Input } from '../../components/Input';
import { Spinner } from '../../components/Spinner';
import { PageHeader } from '../../components/PageHeader';
import { ApiError } from '../../lib/api';
import { clearToken, getToken } from '../../lib/auth';
import { timeAgo } from '../../lib/format';
import {
  useCreateConnection,
  useCvatConnections,
  useDeleteConnection,
  useTestConnection,
} from '../cvat/api';

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
                onClick={() => { clearToken(); navigate('/login'); }}
              >
                Sign out
              </Button>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="CVAT connections"
            subtitle="Saved CVAT servers. Credentials encrypted at rest with Fernet (CVAT_ENC_KEY in backend/.env)."
          />
          <CardBody>
            <CvatConnections />
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


function CvatConnections() {
  const list = useCvatConnections();
  const create = useCreateConnection();
  const del = useDeleteConnection();
  const test = useTestConnection();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [username, setUsername] = useState('');
  const [secret, setSecret] = useState('');
  const [testResult, setTestResult] = useState<Record<string, string>>({});

  async function onAdd(e: React.FormEvent) {
    e.preventDefault();
    try {
      await create.mutateAsync({
        name: name.trim(), base_url: baseUrl.trim(),
        username: username.trim(), secret,
      });
      setAdding(false);
      setName(''); setBaseUrl(''); setUsername(''); setSecret('');
    } catch {/* shown via create.error */}
  }

  async function onTest(id: string) {
    setTestResult((m) => ({ ...m, [id]: '…' }));
    try {
      const r = await test.mutateAsync(id);
      setTestResult((m) => ({ ...m, [id]: '✓ ' + (r.server || 'connected') }));
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      setTestResult((m) => ({ ...m, [id]: '✗ ' + msg.slice(0, 60) }));
    }
  }

  const createErr = create.error instanceof ApiError ? create.error.message : null;

  return (
    <div className="space-y-3">
      {list.isLoading && <Spinner />}
      {list.data && list.data.items.length === 0 && !adding && (
        <p className="text-sm text-slate-500">No CVAT connections yet.</p>
      )}

      {list.data && list.data.items.map((c) => (
        <div key={c.id} className="flex items-start justify-between gap-3 rounded-md border border-slate-200 px-3 py-2">
          <div className="min-w-0 flex-1">
            <div className="font-medium text-slate-900">{c.name}</div>
            <div className="text-[11px] text-slate-500">{c.base_url} · {c.username}</div>
            <div className="text-[10px] text-slate-400">
              Created {timeAgo(c.created_at)}
              {c.last_used_at && ` · used ${timeAgo(c.last_used_at)}`}
            </div>
            {testResult[c.id] && (
              <div className="mt-1 text-[11px] font-mono text-slate-700">{testResult[c.id]}</div>
            )}
          </div>
          <div className="flex flex-col gap-1">
            <Button variant="secondary" onClick={() => onTest(c.id)} loading={test.isPending}>
              Test
            </Button>
            <Button
              variant="danger"
              onClick={async () => {
                if (confirm(`Delete CVAT connection "${c.name}"?`)) {
                  await del.mutateAsync(c.id);
                }
              }}
            >
              Delete
            </Button>
          </div>
        </div>
      ))}

      {!adding && (
        <div className="flex justify-end">
          <Button onClick={() => setAdding(true)}>Add connection</Button>
        </div>
      )}

      {adding && (
        <form onSubmit={onAdd} className="space-y-3 rounded-md border border-dashed border-slate-300 bg-slate-50 p-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Name" hint="A short label.">
              <Input value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} />
            </Field>
            <Field label="Base URL" hint="e.g. https://cvat.example.com">
              <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} required type="url" />
            </Field>
            <Field label="Username">
              <Input value={username} onChange={(e) => setUsername(e.target.value)} required />
            </Field>
            <Field label="Token or password" hint="Stored encrypted (Fernet). 40+ char alnum = API token, else logged in.">
              <Input type="password" value={secret} onChange={(e) => setSecret(e.target.value)} required />
            </Field>
          </div>
          {createErr && (
            <p className="whitespace-pre-line rounded bg-red-50 px-3 py-2 text-xs text-red-700">
              {createErr}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" type="button" onClick={() => setAdding(false)}>Cancel</Button>
            <Button type="submit" loading={create.isPending}
                    disabled={!name.trim() || !baseUrl.trim() || !username.trim() || !secret}>
              Save connection
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
