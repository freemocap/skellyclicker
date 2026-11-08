import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {fileURLToPath, pathToFileURL} from 'node:url';

const require = createRequire(new URL('../skellyclicker-ui/package.json', import.meta.url));
const ui = fileURLToPath(new URL('../skellyclicker-ui/', import.meta.url));
const args = process.argv.slice(2);
if (['dev', 'build'].includes(args[0])) await import('./prepare-desktop.mjs');

let vite;
try {
  const env = {...process.env};
  if (args[0] === 'dev' && !args.includes('--help') && !args.includes('-h')) {
    const {createServer} = await import(pathToFileURL(require.resolve('vite')).href);
    vite = await createServer({root: ui, server: {host: '127.0.0.1', strictPort: false}});
    await vite.listen();
    const origin = 'http://127.0.0.1:' + vite.httpServer.address().port;
    console.log('SkellyClicker dev UI: ' + origin);
    env.SKELLYCLICKER_DEV_ORIGIN = origin;
    // Vite already owns this port. Tauri must load it without starting another server.
    args.splice(1, 0, '--config', JSON.stringify({build: {devUrl: origin, beforeDevCommand: null}}));
  }
  const child = spawn(process.execPath, [require.resolve('@tauri-apps/cli/tauri.js'), ...args], {
    cwd: fileURLToPath(new URL('../native/', import.meta.url)), stdio: 'inherit', windowsHide: true, env,
  });
  const [code] = await once(child, 'exit');
  process.exitCode = code ?? 1;
} finally {
  await vite?.close();
}
