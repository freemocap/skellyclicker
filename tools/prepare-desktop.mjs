import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
const root = fileURLToPath(new URL('../', import.meta.url));
const backend = resolve(root, 'backend');
for (const args of [
  ['sync', '--locked', '--project', backend],
  ['run', '--project', backend, 'python', '-m', 'freemocap_sdk.bundle',
    '--entrypoint', resolve(backend, 'desktop_entry.py'), '--name', 'skellyclicker-backend',
    '--output', resolve(root, 'native/binaries'), '--work', resolve(root, '.test-artifacts/desktop-bundle')],
]) {
  const result = spawnSync('uv', args, {cwd: root, stdio: 'inherit', windowsHide: true});
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
