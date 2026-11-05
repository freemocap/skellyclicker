import {fileURLToPath} from 'node:url';
import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react({exclude: [/\.worker\.[jt]sx?$/]})],
  resolve: {dedupe: ['react', 'react-dom']},
  optimizeDeps: {exclude: ['@freemocap/ui']},
  worker: {format: 'es'},
  server: {
    port: 5176,
    strictPort: true,
    fs: {allow: [
      fileURLToPath(new URL('.', import.meta.url)),
      fileURLToPath(new URL('.', import.meta.resolve('@freemocap/ui'))),
    ]},
  },
});
