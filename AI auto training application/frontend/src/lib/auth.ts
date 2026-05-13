/**
 * v1 single-user auth: a static API_TOKEN pasted on the login page,
 * stored in localStorage, sent as `Authorization: Bearer …` on every call.
 *
 * When multi-user JWT lands, replace this module's surface (getToken,
 * setToken, clearToken) — nothing else has to change.
 */

const KEY = 'aiat.api_token';

export function getToken(): string | null {
  return typeof window !== 'undefined' ? localStorage.getItem(KEY) : null;
}

export function setToken(token: string): void {
  localStorage.setItem(KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(KEY);
}

export function isAuthed(): boolean {
  return !!getToken();
}
