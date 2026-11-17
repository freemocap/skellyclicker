import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {existsSync, readFileSync, writeFileSync} from 'node:fs';
import {join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const ui = fileURLToPath(new URL('../skellyclicker-ui/', import.meta.url));
const {dependencies} = JSON.parse(readFileSync(join(ui, 'package.json'), 'utf8'));

function npm(cwd, ...args) {
  const windows = process.platform === 'win32';
  const result = spawnSync(windows ? 'npm.cmd' : 'npm', args, {
    cwd, shell: windows, stdio: 'inherit', windowsHide: true,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`npm ${args.join(' ')} failed in ${cwd}`);
}

function install(cwd, entryPoints) {
  const modules = join(cwd, 'node_modules');
  const stamp = join(modules, '.skellyclicker-install');
  const hash = createHash('sha256').update(process.version);
  for (const file of ['package.json', 'package-lock.json']) hash.update(readFileSync(join(cwd, file)));
  const fingerprint = hash.digest('hex');
  if (existsSync(stamp) && readFileSync(stamp, 'utf8') === fingerprint &&
      entryPoints.every(file => existsSync(join(modules, file)))) return;
  // Reconcile an existing tree in place: another Vite window may own esbuild.exe.
  const args = existsSync(modules) ? ['install', '--no-save'] : ['ci'];
  npm(cwd, ...args, '--include=dev', '--no-audit', '--no-fund');
  writeFileSync(stamp, fingerprint);
}

for (const name of ['@freemocap/client', '@freemocap/ui']) {
  const cwd = resolve(ui, dependencies[name].slice('file:'.length));
  install(cwd, ['typescript/bin/tsc']);
  npm(cwd, 'run', 'build');
}
install(ui, ['vite/package.json', '@tauri-apps/cli/tauri.js']);
