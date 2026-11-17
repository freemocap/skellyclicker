// Native programs used by playback export and the authored geometry projector.
import {createHash} from 'node:crypto';
import {chmod, copyFile, mkdir, writeFile} from 'node:fs/promises';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';

const ffmpegRelease = 'https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1';
const platform = `${process.platform}-${process.arch}`;
const digests = {
  'win32-x64': [
    '04e1307997530f9cf2fe35cba2ca7e8875ca91da02f89d6c7243df819c94ad00',
    '3a7e2dc003dc2cd1472827e4c7c4f056ae1ae0ae7c5bbc580c99b49827351ba4',
  ],
  'darwin-arm64': [
    'a90e3db6a3fd35f6074b013f948b1aa45b31c6375489d39e572bea3f18336584',
    'bb2db6f5d8cef919da12fbf592119a987202a8c060a886f3cab091f9cab90b64',
  ],
  'linux-x64': [
    'e7e7fb30477f717e6f55f9180a70386c62677ef8a4d4d1a5d948f4098aa3eb99',
    '4f231a1960d83e403d08f7971e271707bec278a9ae18e21b8b5b03186668450d',
  ],
};
if (!digests[platform]) throw new Error(`Unsupported installer target ${platform}`);
const dest = fileURLToPath(new URL('../native/binaries/skellyclicker-backend/tools/', import.meta.url));
await mkdir(dest, {recursive: true});
const ext = process.platform === 'win32' ? '.exe' : '';

async function download(url, filename, sha256) {
  const response = await fetch(url, {signal: AbortSignal.timeout(300_000)});
  if (!response.ok) throw new Error(`${response.status} fetching ${url}`);
  const data = Buffer.from(await response.arrayBuffer());
  if (sha256 && createHash('sha256').update(data).digest('hex') !== sha256) {
    throw new Error(`SHA-256 mismatch for ${url}`);
  }
  await writeFile(filename, data);
}

for (const [index, name] of ['ffmpeg', 'ffprobe'].entries()) {
  const filename = join(dest, name + ext);
  await download(`${ffmpegRelease}/${name}-${platform}`, filename, digests[platform][index]);
  await chmod(filename, 0o755);
  execFileSync(filename, ['-version'], {stdio: 'ignore'});
}
const encoders = execFileSync(join(dest, 'ffmpeg' + ext), ['-hide_banner', '-encoders'], {encoding: 'utf8'});
if (!/\blibx264\b/.test(encoders)) throw new Error('Packaged ffmpeg lacks the libx264 video encoder');
for (const name of ['README', 'LICENSE']) {
  await download(`${ffmpegRelease}/${platform}.${name}`, join(dest, `ffmpeg.${name}`));
}
await copyFile(process.execPath, join(dest, 'node' + ext));
await download(`https://raw.githubusercontent.com/nodejs/node/${process.version}/LICENSE`, join(dest, 'node.LICENSE'));
execFileSync(join(dest, 'node' + ext), ['--version'], {stdio: 'inherit'});
