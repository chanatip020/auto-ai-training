import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/Button';
import { Field, Input } from '../../components/Input';
import { api, ApiError } from '../../lib/api';
import { setToken } from '../../lib/auth';

export function LoginPage() {
  const navigate = useNavigate();
  const [token, setTokenInput] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      // Persist first so the api client picks it up.
      setToken(token.trim());
      // Validate by hitting a protected endpoint that requires the token.
      await api.get<{ items: unknown[]; total: number }>('/api/v1/projects?limit=1');
      navigate('/');
    } catch (e) {
      setToken(''); // wipe bad token
      setErr(e instanceof ApiError ? e.message : 'Could not connect to API.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h1 className="text-lg font-semibold text-slate-900">Sign in</h1>
        <p className="mt-1 text-sm text-slate-500">
          v1 single-user. Paste the <code>API_TOKEN</code> from
          <code className="mx-1 rounded bg-slate-100 px-1">backend/.env</code>.
        </p>
        <div className="mt-5 space-y-4">
          <Field label="API token">
            <Input
              type="password"
              autoFocus
              autoComplete="off"
              placeholder="paste token here"
              value={token}
              onChange={(e) => setTokenInput(e.target.value)}
              required
              minLength={8}
            />
          </Field>
          {err && (
            <p className="rounded bg-red-50 px-3 py-2 text-xs text-red-700">
              {err}
            </p>
          )}
          <Button type="submit" className="w-full" loading={loading} disabled={!token}>
            Sign in
          </Button>
        </div>
      </form>
    </div>
  );
}
