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

## Fresh projects and live backend logs

The current native development slice creates and opens fresh projects with linked
ZED SVO originals and a copied STL reference. The Project sidebar accepts a folder
or its ID-bearing manifest; existing folders are never overwritten. File hashes
bind the original media and reference geometry. Calibration remains unqueried
until fresh sample preparation; there is no prior-project import.

The full-width bottom panel uses the SDK's `BottomLogPanel` and `LogStore`, fed by
`TransportService.subscribeToLog` on the existing WebSocket. The app attaches the
SDK `LogHub` during server lifespan and removes it at shutdown. Startup history,
project operations, warnings and Uvicorn messages are actual backend records.
The SDK owns bounded buffering, validation, replay identity and terminal controls.

Run `node tools/desktop.mjs dev --no-watch` for a visible native app with Vite
frontend HMR. Python backend changes require closing the app and rerunning that
command to rebuild its owned frozen backend. SDK UI source changes require the
SDK package build; worker changes may also require a WebView reload. This is not
full-stack hot reload. Release builds still use the established onedir backend.

Validation: `backend/tests/test_projects.py` checks relocation, source integrity,
missing input and path boundaries; `skellyclicker-ui/tests/logs.integration.test.mjs`
checks startup replay and live warnings through the public SDK client. Native
inspection scripts are `tests/native-project-review.mjs` and
`tests/native-live-logs.mjs` in the UI package. Their screenshots/reports belong in
ignored `.test-artifacts/`, and are not production data.

The Project sidebar now composes SDK `RecordingBrowser` for remembered projects
and current recordings, preserving Core's search, sorting, compact rows and
expandable details. Open/New project fields are secondary app-owned dialogs.
The upper-left SDK `ServerConnectionStatus` follows actual TransportService
`state-change` events; its reconnect/disconnect actions only control that socket,
not the desktop-owned backend. HTTP reachability is shown separately.
SkellyClicker explicitly disables the informational playback timing popup and the
redundant log wrapper header; resource errors and log terminal controls remain.
The active workspace is a semantic Project tab. Isolated interaction validation:
`skellyclicker-ui/tests/project-browser-controls.mjs`; passive native evidence:
`skellyclicker-ui/tests/native-project-picker.mjs`. The isolated test stubs only
native endpoint discovery and uses the real backend/socket; it does not operate
the user's native window.

## Fresh preparation review slice

The Project screen can prepare a bounded range (1–60 source frames) from its linked SVO, then review synchronized rectified images, depth, masks and candidate outlines. The application runs ZED replay and FoundationPose sequentially in explicitly configured external runtimes. The visible mask preset is specific to the current demonstration recording; it is not an arbitrary-object segmentation implementation. Geometry comes from the project's STL snapshot and authored units. The adapter follows the established local runtime setup [@zedBenchyLocalFoundationPose].

SpatialHub converts mesh units to metres and centers geometry. The worker records that transform and writes both original-STL-to-left-camera and original-STL-to-right-camera matrices [@spatialhubLocalPoseAdapter]. Rectified intrinsics, stereo extrinsics and source image timestamps are queried during fresh replay. Depth is a NEURAL replay estimate. Pilot gate passes are machine candidates, never human approval; the right-camera mask agreement is pose-conditioned and the 5 mm depth threshold is a heuristic.

Each attempt writes into a new project `working/preparation/<id>` directory. Cancellation affects only its child process tree. External workers receive null stdin so they cannot inherit the desktop backend's lifecycle control pipe. The frozen backend temporarily clears its DLL search directory for external startup and restores it afterward. SDK package data collection includes both `.worker` sources.

Successful output publishes an immutable `results/<recording>/<attempt>/r001` directory with hashed inventory, calibration, geometry, software and worker provenance, exact int64 timing Parquet, and candidate Parquet. The project `sample_result` selects the result. JSON summaries and PNGs support review; Parquet holds authoritative numerical rows. Rejected candidates remain inspectable. Failed/cancelled attempts remain on disk and are not resumed automatically. Closing/reopening loads the selected published result, not an interrupted job.

This slice provides image-sequence review, not encoded video, full 3D playback, point clouds, manual label approval or training. Runtime paths can be configured with `SKELLYCLICKER_ZED_RUNTIME`, `SKELLYCLICKER_ZED_SDK_BIN`, and `SKELLYCLICKER_POSE_DLLS`. Runtime availability is reported by `/api/preparation/runtime`; the application reports job failures in its live terminal.

Validation: `python -m unittest discover -s backend/tests -p test_preparation.py` checks range bounds, preservation of later poses when the initial row has none, and exact nanosecond storage. From `skellyclicker-ui`, `node tests/preparation-controls.mjs` uses a separate installed Edge session and the running native backend to verify reopening, frame/view selection and completion loading. `node tests/native-fresh-samples.mjs` passively captures native image evidence. `node tests/start-fresh-preparation.mjs` intentionally starts a new real job; do not treat it as a harmless unit test.
