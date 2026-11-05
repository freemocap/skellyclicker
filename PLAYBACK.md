# Desktop playback application

## Source and package boundaries

The app consumes SDK packages through public imports. `@freemocap/ui` owns Core-derived playback controls, synchronized-video presentation, Parquet decoding and the original offscreen 3D worker. `@freemocap/client` owns HTTP/self-describing CBOR transport and image decoding. The Python SDK owns server composition, encoding, desktop readiness/shutdown and bundling. The Rust `freemocap-desktop` crate owns the child process lifetime.

SkellyClicker owns its Tauri identity/window/icons, product shell, `/api/status`, `skellyclicker_state` message schema and backend entry point. The native window is deferred until the SDK reports a ready owned backend, following SkellySpeak's state-before-webview startup pattern [@skellyspeakDesktopReference]. SkellySpeak's backend is not a Python sidecar; that reusable support is supplied by the SDK.

Local npm `file:`, uv editable and Cargo path dependencies point to `../../project/repos/sdk`. No private source aliases or runtime imports from `old/` are used. Replace local package references with versioned SDK artifacts when published.

## Development setup

Windows prerequisites are Node22+, uv, Rust/MSVC and WebView2. Existing installations were verified on this machine; no system-wide prerequisite installation was performed.

1. In each SDK `packages/client` and `packages/ui`, run its documented `npm ci --ignore-scripts` and `npm run build`.
2. In `skellyclicker-ui`, run `npm ci --ignore-scripts`.
3. In `backend`, run `uv sync --locked`.
4. From this repository root, run `node tools/desktop.mjs dev --no-watch`.

The desktop wrapper runs the SDK PyInstaller onedir bundler before Tauri. Its output includes Python and required packages, then Tauri maps the whole directory to bundled `backend/` resources. The SDK starts this hidden child, announces readiness only after ASGI startup and socket binding, and closes it on app exit. The native window obtains its endpoint through `backend_url`; HTTP and WebSocket remain the application transport.

Desktop backend uses an available loopback port, distinct from Core's current default53117 in verified runs. It never kills or attaches to another service. The browser-only diagnostic entry remains `uv run skellyclicker-playback` (default8006, configurable) and `npm run dev` (5176); it is not the user distribution.

## Windows distribution

Run `node tools/desktop.mjs build` from the repository root. This builds the frontend, native application and NSIS installer with the backend resources. The release executable was copied with its bundled backend to an independent portable directory and verified with no dev server. Its WebView served http://tauri.localhost/, obtained its owned backend through IPC, passed HTTP/WS and image decoding, and closed both processes with the window. No signing, public release upload or other-platform verification is included in this local milestone.

## Verification

- `backend/.venv/Scripts/python.exe -B backend/tests/check_lifecycle.py`: actual SDK runner startup, HTTP and graceful signal shutdown/port release.
- `npm run test:backend` from the frontend: HTTP identity and two independently validated binary state updates (requires diagnostic backend8006).
- `node tests/inspect-shell.mjs`: branding, empty playback canvas, original worker and absence of capture navigation/browser errors (requires UI5176/backend8006).
- `node tests/image-roundtrip.mjs`: real JPEG through Python SDK CBOR packing, JS unpacking and browser SDK pixel decode (requires frontend dev server).
- `node tests/inspect-native.mjs`: actual Tauri WebView, backend IPC discovery, HTTP/WS status and SDK image decode; attach through test-only local WebView CDP. `SKELLYCLICKER_NATIVE_LABEL` separates evidence files.
- `backend/.venv/Scripts/python.exe -B tools/check_references.py`: source-reference validation.

Screenshots and reports live in ignored `.test-artifacts/`. Native development evidence is separate from built/installed distribution evidence. The delivered UI is an empty workspace, not verified loaded-recording playback. Large renderer/Parquet bundle warnings remain; no worker/performance redesign was introduced.

Verified artifacts:
- `native/target/release/bundle/portable/SkellyClicker_0.1.0_windows_x64.zip` (launch-tested portable directory; unzip and open SkellyClicker/skellyclicker.exe).
- `native/target/release/bundle/nsis/SkellyClicker_0.1.0_x64-setup.exe` (built, unsigned, not installed during this check).

Evidence: `.test-artifacts/native-dev.json/.png` records development mode; `.test-artifacts/native-portable.json/.png` records the built WebView and image result; `.test-artifacts/native-portable-shutdown.json` records normal close, owned process exit and port release. All test windows and task-owned servers were closed afterward. Desktop runtime does not need the source checkout, Python environment or npm server.

SDK integration baseline: `freemocap/sdk` commit `eacdc6f6f9ec737a48892fd68513e7954f4fb0e3` on `sfn26`; app tests exercised the editable sources that became that commit. The package manifests and lockfiles retain the local development links.
