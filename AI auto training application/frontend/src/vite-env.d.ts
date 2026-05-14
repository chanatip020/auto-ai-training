/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Fallback module declarations so type-check works even if `vite/client`
// types aren't resolved yet (e.g. fresh checkout before `npm install`).
declare module '*.css';
declare module '*.svg';
declare module '*.png';
declare module '*.jpg';
