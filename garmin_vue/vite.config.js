import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon-192.png', 'icon-512.png', 'apple-touch-icon.png'],
      manifest: {
        name: 'Dashboard Garmin',
        short_name: 'Garmin',
        description: 'Métricas e análise dos dados Garmin Connect',
        theme_color: '#0f111b',
        background_color: '#0f111b',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' },
        ],
      },
      workbox: {
        // Não faz cache do JSON grande — sempre busca da rede
        runtimeCaching: [
          {
            urlPattern: /\/garmin_data\.json$/,
            handler: 'NetworkFirst',
            options: { cacheName: 'garmin-data', networkTimeoutSeconds: 10 },
          },
        ],
      },
    }),
  ],
})
