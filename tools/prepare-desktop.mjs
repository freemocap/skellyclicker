import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const args = ['run', '--locked', '--project', 'backend', 'python', 'tools/backend_bundle.py'];
if (process.argv[2] !== 'dev') args.push('--force');
const result = spawnSync('uv', args, {cwd:root, stdio:'inherit', windowsHide:true});
if (result.error) throw result.error;
if (result.status !== 0) process.exit(result.status ?? 1);
