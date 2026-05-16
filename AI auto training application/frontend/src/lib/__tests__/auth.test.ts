import { afterEach, describe, expect, it } from 'vitest';
import { clearToken, getToken, isAuthed, setToken } from '../auth';

describe('auth token storage', () => {
  afterEach(() => clearToken());

  it('returns null when no token is set', () => {
    expect(getToken()).toBeNull();
    expect(isAuthed()).toBe(false);
  });

  it('round-trips a token through localStorage', () => {
    setToken('hello-world-token-123');
    expect(getToken()).toBe('hello-world-token-123');
    expect(isAuthed()).toBe(true);
  });

  it('clearToken removes the value', () => {
    setToken('to-be-cleared');
    clearToken();
    expect(getToken()).toBeNull();
    expect(isAuthed()).toBe(false);
  });
});
