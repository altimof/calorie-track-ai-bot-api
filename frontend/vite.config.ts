import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],

  resolve: {
    alias: { '@': '/src' },
  },

  server: {
    port: 3000,
    host: '0.0.0.0',
  },

  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: 'react-vendor',
              test: /[\\/]node_modules[\\/](react|react-dom|react-router-dom)[\\/]/,
            },
            { name: 'chart-vendor', test: /[\\/]node_modules[\\/]recharts[\\/]/ },
            {
              name: 'i18n-vendor',
              test: /[\\/]node_modules[\\/](i18next|react-i18next)[\\/]/,
            },
          ],
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
});
