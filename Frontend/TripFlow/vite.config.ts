import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const proxy = { '/api': 'http://127.0.0.1:5080' }

export default defineConfig({
  plugins: [react()],
  server: { proxy },
  preview: { proxy },
})
