import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { formatBytes, formatTime, num, timeAgo } from '../format';

describe('formatBytes', () => {
  it.each([
    [null, '—'],
    [undefined, '—'],
    [0, '0 B'],
    [512, '512 B'],
    [1024, '1.0 KB'],
    [1024 * 1024, '1.0 MB'],
    [1024 * 1024 * 1024 * 2, '2.0 GB'],
  ])('formats %s as %s', (input, expected) => {
    expect(formatBytes(input)).toBe(expected);
  });
});

describe('num', () => {
  it('rounds to the requested precision', () => {
    expect(num(0.123456, 2)).toBe('0.12');
    expect(num(0.123456, 4)).toBe('0.1235');
  });

  it('returns em-dash for null/undefined', () => {
    expect(num(null)).toBe('—');
    expect(num(undefined)).toBe('—');
  });
});

describe('formatTime', () => {
  it('returns em-dash for empty', () => {
    expect(formatTime(null)).toBe('—');
    expect(formatTime(undefined)).toBe('—');
  });

  it('formats a valid ISO date', () => {
    // We don't pin the locale — just make sure it returns something non-empty.
    const result = formatTime('2026-05-14T10:30:00Z');
    expect(result.length).toBeGreaterThan(0);
    expect(result).not.toBe('—');
  });
});

describe('timeAgo', () => {
  const realNow = Date.now;
  beforeEach(() => {
    Date.now = vi.fn(() => new Date('2026-05-14T12:00:00Z').getTime());
  });
  afterEach(() => {
    Date.now = realNow;
  });

  it.each([
    ['2026-05-14T11:59:30Z', '30s ago'],
    ['2026-05-14T11:55:00Z', '5m ago'],
    ['2026-05-14T09:00:00Z', '3h ago'],
    ['2026-05-12T12:00:00Z', '2d ago'],
  ])('formats %s as %s', (input, expected) => {
    expect(timeAgo(input)).toBe(expected);
  });

  it('handles null/undefined', () => {
    expect(timeAgo(null)).toBe('—');
    expect(timeAgo(undefined)).toBe('—');
  });
});
