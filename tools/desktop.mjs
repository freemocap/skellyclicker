import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const require = createRequire(new URL('../skellyclicker-ui/package.json', import.meta.url));
if (['dev', 'build'].includes(process.argv[2])) await import('./prepare-desktop.mjs');
const child = spawn(process.execPath, [require.resolve('@tauri-apps/cli/tauri.js'), ...process.argv.slice(2)], {
  cwd: fileURLToPath(new URL('../native', import.meta.url)), stdio: 'inherit', windowsHide: true,
});
child.on('error', error => {console.error(error); process.exitCode = 1;});
child.on('exit', code => {process.exitCode = code ?? 1;});
