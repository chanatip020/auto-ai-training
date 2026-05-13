import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Match the design doc's status pill palette.
        status: {
          created: '#9ca3af',
          uploaded: '#3b82f6',
          analyzed: '#0d9488',
          ready: '#16a34a',
          training: '#f59e0b',
          completed: '#059669',
          failed: '#dc2626',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
} satisfies Config;
