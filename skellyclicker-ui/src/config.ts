export const backendUrl = (import.meta.env.VITE_SKELLYCLICKER_BACKEND_URL || 'http://127.0.0.1:8006').replace(/\/$/, '');
const parsedBackendUrl = new URL(backendUrl);
if (!['http:', 'https:'].includes(parsedBackendUrl.protocol)) {
  throw new Error('VITE_SKELLYCLICKER_BACKEND_URL must use HTTP or HTTPS.');
}
