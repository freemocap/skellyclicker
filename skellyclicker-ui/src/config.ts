import {invoke, isTauri} from '@tauri-apps/api/core';

export async function resolveBackendUrl(): Promise<string> {
  const endpoint = isTauri()
    ? await invoke<string>('backend_url')
    : (import.meta.env.VITE_SKELLYCLICKER_BACKEND_URL || 'http://127.0.0.1:8006');
  const parsed = new URL(endpoint);
  if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('Backend endpoint must use HTTP or HTTPS.');
  return endpoint.replace(/\/$/, '');
}
