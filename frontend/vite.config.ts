import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // Backend routes live at root (/settings, /projects, ...). The
        // frontend namespaces calls under /api; strip that prefix so the
        // proxy forwards to the real backend path.
        rewrite: (path: string) => path.replace(/^\/api/, ''),
      },
    },
  },
})
