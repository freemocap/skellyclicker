import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
function runBackend(...args) {
  const result = spawnSync('uv', ['run','--locked','--project','backend','python',...args],
    {cwd:root, stdio:'inherit', windowsHide:true});
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
const dev = process.argv[2] === 'dev';
if (dev) runBackend('-m', 'skellyclicker_app.gpu_runtime', '--prepare-dev-training');
runBackend('tools/backend_bundle.py', ...(dev ? [] : ['--force']));
