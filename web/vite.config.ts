import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [
    react(),
    {
      name: 'fc-bootstrap-dev-stub',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          const path = req.url?.split('?')[0] ?? ''
          if (path === '/app/fc-bootstrap.js') {
            res.setHeader('Content-Type', 'application/javascript; charset=utf-8')
            res.end('// Dev: use VITE_API_TOKEN from .env; production uses Gateway /app/fc-bootstrap.js\n')
            return
          }
          next()
        })
      },
    },
  ],
})
