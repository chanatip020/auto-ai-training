import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// Tear down DOM after every test
afterEach(() => {
  cleanup();
});

// jsdom doesn't ship matchMedia; some Tailwind/recharts code expects it.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (q: string) => ({
    matches: false,
    media: q,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// localStorage is in jsdom by default, but make sure it starts clean per test
afterEach(() => {
  localStorage.clear();
});
