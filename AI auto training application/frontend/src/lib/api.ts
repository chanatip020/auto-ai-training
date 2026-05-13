/**
 * Thin typed wrapper around fetch. Uses the response envelope from the API
 * — every endpoint returns { data, error, meta }. Errors raise ApiError so
 * TanStack Query can route them to its onError handlers.
 */
import { getToken, clearToken } from './auth';
import type { Envelope } from './types';

const BASE = (import.meta.env.VITE_API_BASE as string) || '';

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  isFormData?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...((opts.headers as Record<string, string>) || {}),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (opts.isFormData) {
    body = opts.body as BodyInit;
    // Do NOT set Content-Type for FormData — the browser sets the boundary.
  } else if (opts.body !== undefined && opts.body !== null) {
    body = JSON.stringify(opts.body);
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(`${BASE}${path}`, {
    method: opts.method || 'GET',
    headers,
    body,
  });

  if (res.status === 204) return undefined as T;

  let payload: Envelope<T> | { detail?: string } | undefined;
  try {
    payload = await res.json();
  } catch {
    payload = undefined;
  }

  if (!res.ok) {
    if (res.status === 401) {
      clearToken();
    }
    const err = (payload as Envelope<T> | undefined)?.error;
    throw new ApiError(
      err?.code || 'HTTP_ERROR',
      err?.message || `HTTP ${res.status}`,
      res.status,
      err?.details || {},
    );
  }

  const env = payload as Envelope<T>;
  if (env?.error) {
    throw new ApiError(env.error.code, env.error.message, res.status, env.error.details);
  }
  return env?.data as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: 'POST', body: formData, isFormData: true }),
};

/** Build an absolute API URL. Used for opening downloads in a new tab. */
export function apiUrl(path: string): string {
  return `${BASE}${path}`;
}
