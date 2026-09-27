import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'

export default defineConfig(({ command }) => ({
  plugins: [react()],
  server: command === 'serve' ? {
    host: 'localhost', port: 5173, strictPort: true,
    https: {
      cert: readFileSync(new URL('../backend/.certs/localhost-cert.pem', import.meta.url)),
      key: readFileSync(new URL('../backend/.certs/localhost-key.pem', import.meta.url)),
    },
  } : undefined,
}))
