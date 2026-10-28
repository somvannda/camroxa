import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  if (mode === 'production') {
    const apiBase = env.VITE_API_BASE_URL?.trim() ?? '';
    if (/localhost|127\.0\.0\.1/i.test(apiBase)) {
      throw new Error(
        'Refusing production build: VITE_API_BASE_URL must not point at localhost. ' +
          'Use an empty .env.production (same-origin /api via nginx) or a public API URL.',
      );
    }
  }

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': {
          target: env.VITE_API_PROXY_TARGET?.trim() || 'http://127.0.0.1:8000',
          changeOrigin: true,
          // Strip Domain so the cookie binds to whatever host the browser used
          // (localhost vs 127.0.0.1).
          cookieDomainRewrite: '',
        },
      },
    },
  };
});