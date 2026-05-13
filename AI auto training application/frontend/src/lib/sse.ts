/**
 * SSE hook for live training metrics + status.
 *
 * The backend's /sse/training/{id} endpoint requires an Authorization header,
 * but the browser EventSource API can't send custom headers. So this hook
 * uses fetch + ReadableStream parsing instead — that lets us pass the bearer
 * token cleanly and still get the real-time stream.
 */
import { useEffect, useRef, useState } from 'react';
import { getToken } from './auth';

const BASE = (import.meta.env.VITE_API_BASE as string) || '';

export interface SSEEvent {
  type: string;
  [k: string]: unknown;
}

export function useSSE(path: string | null, onEvent: (ev: SSEEvent) => void) {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cbRef = useRef(onEvent);
  cbRef.current = onEvent;

  useEffect(() => {
    if (!path) return;
    const ctrl = new AbortController();
    const token = getToken();

    (async () => {
      try {
        setError(null);
        const res = await fetch(`${BASE}${path}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
          signal: ctrl.signal,
        });
        if (!res.ok || !res.body) {
          setError(`SSE connect failed: ${res.status}`);
          return;
        }
        setConnected(true);

        const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
        let buf = '';
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += value;
          // SSE messages are separated by \n\n
          let split;
          while ((split = buf.indexOf('\n\n')) !== -1) {
            const frame = buf.slice(0, split);
            buf = buf.slice(split + 2);
            const ev = parseFrame(frame);
            if (ev) {
              try { cbRef.current(ev); } catch (e) { console.error(e); }
            }
          }
        }
      } catch (e) {
        if ((e as DOMException).name !== 'AbortError') {
          setError(String(e));
        }
      } finally {
        setConnected(false);
      }
    })();

    return () => ctrl.abort();
  }, [path]);

  return { connected, error };
}

function parseFrame(frame: string): SSEEvent | null {
  // Ignore comments (lines starting with ":") and empty frames.
  if (!frame.trim() || frame.trim().startsWith(':')) return null;
  let data = '';
  let event = '';
  for (const line of frame.split('\n')) {
    if (line.startsWith('data:')) data += line.slice(5).trimStart();
    else if (line.startsWith('event:')) event = line.slice(6).trim();
  }
  if (!data) return null;
  try {
    const parsed = JSON.parse(data) as SSEEvent;
    if (event && !parsed.type) parsed.type = event;
    return parsed;
  } catch {
    return null;
  }
}
