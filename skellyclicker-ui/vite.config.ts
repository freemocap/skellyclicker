import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react({exclude: [/\.worker\.[jt]sx?$/]})],
  resolve: {dedupe: ['react', 'react-dom']},
  worker: {format: 'es'},
  server: {port: 5176, strictPort: true},
});
