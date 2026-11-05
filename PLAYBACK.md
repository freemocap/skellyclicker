# SkellyClicker playback shell

This first milestone runs the original Core-derived playback components through public SDK packages, with SkellyClicker branding and a separate backend. It opens an **empty playback workspace**: no recording selector/resource adapter, real video playback, labeling, training or pose editing is delivered in this milestone. The legacy labeling application and its environment remain separate.

## Launch

Requires Node 22 or newer, uv, and the sibling SDK checkout at `../../project/repos/sdk`. Build the SDK's client and UI packages with their documented `npm ci --ignore-scripts` and `npm run build` commands first. The Python SDK server is installed as an editable package by the backend configuration.

From this repository, in two terminals:

```powershell
cd backend
uv sync --locked
uv run skellyclicker-playback
```

```powershell
cd skellyclicker-ui
npm ci --ignore-scripts
npm run dev
```

Open http://127.0.0.1:5176. Stop each process with Ctrl+C in its terminal.

The backend defaults to `127.0.0.1:8006`, distinct from Core's current default `53117`. Override it with `--port` or `SKELLYCLICKER_PORT`; set the frontend's matching endpoint with `VITE_SKELLYCLICKER_BACKEND_URL`. The app binds locally and never kills another server to claim its port. Frontend origin port5176 is explicitly allowed by the app's backend CORS/WebSocket configuration.

## Package boundary

The frontend imports `PlaybackWorkspace` and `styles.css` from `@freemocap/ui`, and HTTP/transport helpers from `@freemocap/client`. The SDK owns playback controls, synchronized video presentation, Parquet decoding and the original offscreen 3D worker. SkellyClicker owns branding, navigation, server configuration, `/api/status` and its independently validated `skellyclicker_state` messages.

Local npm `file:` dependencies and the uv editable source enable parallel SDK development. Vite excludes the UI package from prebundling and permits its installed built-asset directory so workers/fonts resolve. There are no private Core/SDK source aliases. Versioned package artifacts can replace local development dependencies later.

## Verification

With both servers running, from `skellyclicker-ui`:

```powershell
npm run build
npm run test:backend
node tests/inspect-shell.mjs
node tests/image-roundtrip.mjs
```

From the repository root:

```powershell
backend/.venv/Scripts/python.exe -B backend/tests/check_lifecycle.py
```

Browser checks use installed Microsoft Edge by default; set `SKELLYCLICKER_BROWSER_CHANNEL` to another installed Playwright-supported channel if needed. The screenshot is saved under ignored `.test-artifacts/playback-shell.png`.

Verified on Windows: HTTP identity; initial and request-response binary state updates through SDK validation; a real JPEG through Python CBOR/image packing, JS unpacking and browser pixel decoding; actual SDK runner startup, graceful signal shutdown and port release; visible branding, playback controls and worker canvas without capture navigation or browser errors; production build including both worker assets. Pillow is a test-only dependency for producing the image fixture in memory.

Visual review compared the rendered shell with Core's playback layout source and existing playback screenshot: shared theme/fonts, sidebar/content proportions, video/3D division and timeline controls are retained. The product sidebar is intentionally limited to branding and an empty recording section; Core calibration/processing controls are not wired. This is not pixel-identical Core or evidence of loaded-recording playback. Large renderer/Parquet worker bundle warnings remain; no performance redesign was introduced.
