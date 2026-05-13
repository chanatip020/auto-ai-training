import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// API target for the dev proxy.
//   - Native dev (`npm run dev` on host)   : default = http://localhost:8000
//   - Dev inside docker compose            : docker-compose.override.yml sets
//                                            API_PROXY_TARGET=http://api:8000
const API_PROXY_TARGET = process.env.API_PROXY_TARGET || 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,    // bind 0.0.0.0 so docker port-forward works
    proxy: {
      '/api': {
        target: API_PROXY_TARGET,
        changeOrigin: true,
        // SSE / streaming endpoints need ws-style passthrough
        ws: false,
      },
    },
  },
});
