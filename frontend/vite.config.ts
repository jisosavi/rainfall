import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    // The built site is served from this path on the test server.
    base: env.VITE_BASE || '/test/rainfall/',
    plugins: [vue()],
    server: {
      // In dev, /api is proxied to the backend, so no CORS setup is needed for localhost.
      proxy: {
        '/api': { target: env.DEV_API_PROXY || 'https://rainfall-production.up.railway.app', changeOrigin: true },
      },
    },
    worker: { format: 'es' },
    build: {
      // maplibre-gl and deck.gl are large by nature.
      chunkSizeWarningLimit: 2500,
    },
  }
})
