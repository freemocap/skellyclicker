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

The Project screen can prepare a bounded range (1–900 source frames) from its linked SVO, then publish buffered stereo videos and a derived SDK display revision with synchronized fitted STL surfaces and geometric control points. Depth and mask artifacts remain in the source result. The application runs ZED replay and FoundationPose sequentially in explicitly configured external runtimes. The visible mask preset is specific to the current demonstration recording; it is not an arbitrary-object segmentation implementation. Geometry comes from the project's STL snapshot and authored units. The adapter follows the established local runtime setup [@zedBenchyLocalFoundationPose].

SpatialHub converts mesh units to metres and centers geometry. The worker records that transform and writes both original-STL-to-left-camera and original-STL-to-right-camera matrices [@spatialhubLocalPoseAdapter]. Rectified intrinsics, stereo extrinsics and source image timestamps are queried during fresh replay. Depth is a NEURAL replay estimate. Pilot gate passes are machine candidates, never human approval; the right-camera mask agreement is pose-conditioned and the 5 mm depth threshold is a heuristic.

Each attempt writes into `recordings/<recording>/skellyclicker/working/preparation/<id>`. Cancellation affects only its child process tree. External workers receive null stdin so they cannot inherit the desktop backend's lifecycle control pipe. The frozen backend temporarily clears its DLL search directory for external startup and restores it afterward. SDK package data collection includes the external `.worker` sources and SDK recording-path resources.

Successful output publishes an immutable `recordings/<recording>/skellyclicker/results/<attempt>/r001` directory with hashed inventory, calibration, geometry, software and worker provenance, exact int64 timing Parquet, and candidate Parquet. The project `sample_result` selects the result. JSON summaries and PNGs support review; Parquet holds authoritative numerical rows. Rejected candidates remain inspectable. Failed/cancelled attempts remain on disk and are not resumed automatically. Closing/reopening loads the selected published result, not an interrupted job.

The Project screen uses the SDK PlaybackWorkspace for buffered H.264 stereo video and recorded 3D model playback. It loads numerical Parquet once per revision; normal playback never requests per-frame PNGs. Point clouds, manual label approval and training remain later work. Runtime paths can be configured with `SKELLYCLICKER_ZED_RUNTIME`, `SKELLYCLICKER_ZED_SDK_BIN`, and `SKELLYCLICKER_POSE_DLLS`. Runtime availability is reported by `/api/preparation/runtime`; the application reports job failures in its live terminal.

Validation: `python -m unittest discover -s backend/tests -p test_preparation.py` checks range bounds, preservation of later poses when the initial row has none, and exact nanosecond storage. From `skellyclicker-ui`, `node tests/integrated-playback-controls.mjs` uses a separate installed Edge session and the running native backend to verify video playback, scrubbing, actual model-buffer alignment with both browser-presented frames, network behavior and all pane resize boundaries. Set SKELLYCLICKER_TEST_CDP_PORT to an isolated native instance to run the same checks in WebView2. `node tests/native-integrated-playback.mjs` passively captures the main native window. `node tests/start-fresh-preparation.mjs` intentionally starts a new real job; do not treat it as a harmless unit test.

## Integrated SDK playback boundary

`playback_adapter.py` converts the selected fresh result into an immutable `recordings/<recording>/skellyclicker/playback/<revision>` display artifact. It uses Forge's public rigid STL definition and coordinate conversion APIs [@forgeRigidStlAdapter], then the SDK manifest, dense channel writer, recording router and existing PlaybackWorkspace [@sdkRecordedPlayback]. Core is not imported. Source int64 nanoseconds remain authoritative; relative display seconds and encoded-video indices map explicitly back to source frames.

The three models distinguish finite candidates that passed pilot gates (green), finite rejected candidates (orange), and the unposed authored STL reference at world origin (purple). Missing state channels contain NaN, never a fabricated pose. The actual STL surface is simplified for display, with original geometry hash and invertible source/segment transforms retained. Eight derived bounding-box landmarks are geometric control points, not detector predictions or approved labels. They are projected onto annotated videos from the same candidate pose. Measured display values use millimetres in Blender axes; rectified optical-camera conversion occurs once at the adapter boundary. The static reference placement is a comparison aid, not a measured observation.

Original and annotated stereo videos use browser-compatible H.264 with faststart and SDK byte-range/caching support. Parquet carries the self-describing display manifest and provenance. The UI uses the SDK's existing offscreen renderer and bounded buffer ownership, not another renderer. The sidebar, media/3D split, camera tile grid and bottom log panel are resizable. Preparation controls stay in the sidebar and never replace playback.

Run `backend/.venv/Scripts/python.exe tools/verify_playback.py <project-folder>` to compare stored display rotations/positions and stereo projections against the authoritative pose result, and to check media counts and hashes. Its explicit 0.001 mm/pixel numerical tolerance accommodates float32 pose-matrix orthogonality error during unit-quaternion conversion; it is not a claim of physical measurement accuracy. The current dataset is a one-second bounded sample, not the full recording.


### Explicit scene frame and themed review controls

Playback publishes `reference_frames` and `scene_reference_frames` alongside the
channels and camera geometry. The `blender_world` definition binds camera-to-world
poses and all world-space channels to Blender axes in millimetres. Forge's maintained
canonical convention is loaded at the app's optical-camera boundary and bundled
with the desktop backend. ZED acquisition explicitly selects its IMAGE convention.
No camera-only display rotation or inverse producer compensation belongs in this
path. The SDK retains the frame definition through playback selection and worker
calibration delivery [@forgeRigidStlAdapter; @sdkRecordedPlayback].

The preparation form uses the SDK `ControlSection`, `NumberField`, and `ButtonSm`;
the scene legend uses `Legend`. Its swatches distinguish passed gates, rejected
candidates, and the unposed authored reference. All candidates remain unreviewed.
Details explain derived bounding-box points and the reference placement. Invalid
source ranges disable preparation; inspection never starts a job automatically.

The scene audit additionally checks independent expected optical-axis directions,
the recorded stereo baseline, positive full-mesh camera depth, and full original
STL projections on raw source frames 12 and 21. The separate synthetic test uses
a nonidentity stereo rotation to expose inverse/composition mistakes. These checks
supplement numerical serialization tests; they do not establish training-label
accuracy or human acceptance. The actual-camera checks in `verify_playback.py`
are specific to the current rectified ZED review fixture.


## Recording folder contract

The SDK `RecordingStructure` supplies shared paths; SkellyClicker supplies its
source adapter and application extension. Preparing the first bounded pose sample
also materializes the full source as rectified synchronized H.264 views. Later
attempts verify and reuse those hashed inputs. Exact source nanoseconds and frame
indices remain in timing sidecars; encoded video time is not the source clock.

```text
recordings/<recording>/
  <recording>_recording_info.json
  <recording>_calibration.toml
  videos/
    stereo/<recording>_stereo_sources.json
    synchronized/left.mp4, right.mp4
    synchronized/clips/<revision>/synchronized-left.mp4, synchronized-right.mp4
    annotated/clips/<revision>/annotated-left.mp4, annotated-right.mp4
  skellyclicker/
    inputs/<revision>/
    results/<attempt>/r001/
    playback/<revision>/
    working/
    updates/
```

SDK timing files accompany the synchronized views. The stereo manifest explicitly
links the hashed original SVO and factory configuration; these external originals
are not copied or silently relocated. Full videos and bounded sample clips have
separate paths. The display revision's `media.json` resolves clips relative to the
project root, and `media_hashes.json` records their identities. Calibration records
queried rectified stereo geometry in millimetres; it does not claim a board solve.

The current recording has 1,519 frames in each full view and 30 frames in each
review clip. Its one-time layout update retains the old result/playback directories
and records the previous project manifest under `skellyclicker/updates/`. Working
staging files are retained as well. These are preserved audit copies, not alternate
selected inputs or an automatic legacy migration interface.

FreeMoCap Core has not been changed or runtime-tested for this layout. Its remaining
legacy video-folder readers need alignment before direct discovery and fresh
processing can be claimed. SDK display Parquet is distinct from Core recording
Parquet: no misleading root `<recording>_data.parquet` is written. Direct Core
processing, portable external-source relinking and saved rigid-result interchange
remain unverified. Native acceptance must cover end/replay, repeated loops and near-end seeks;
ordinary playback and emitted-packet checks do not establish continuous visual
synchronization. Use `tests/reconstruction-playback.mjs --sustained` from the UI
package; set `SKELLYCLICKER_TEST_CDP_PORT` only to an isolated native test window.


## Stereo reconstruction playback

The reconstruction producer retains rectified RGB and full-resolution ZED NEURAL
depth, then projects finite samples on a four-pixel image grid into the declared
Blender world frame in millimetres. Display filtering retains depths from 0.17 to
3 metres. Archived arrays retain the denser grid; display chunks cap each frame
at 25,000 points through deterministic index subsampling. This is stereo-derived
point geometry, not a reconstructed surface or independently validated depth.

The agreed SDK integration uses one persistent point geometry and typed GPU
attributes, explicit update ranges and draw count [@threeBufferAttributes]
[@threeBufferGeometry]. Fifteen-frame self-describing chunks carry the complete
reference definition, source-frame IDs and exact nanosecond clock alongside float32
XYZ and uint8 RGB payloads. Bounded worker fetching and cache ownership belong to
the SDK. No per-point JavaScript objects are created. Short clips preload and retain their complete dense cloud data using the SDK byte budget and configurable concurrency; larger recordings use its rolling cache policy.

The native preparation form accepts up to 900 source frames per job. Jobs expose
progress, cancellation and live logs; the current job can be recovered by the UI
within the same backend session. The first long segment uses source frames90–840
(751frames,25.001002seconds), with751 finite candidate poses:208 passed the
existing pilot gates and543 were rejected. All remain unreviewed. Full-resolution
depth and the source calibration are retained beside the point-cloud archive.

The SDK-backed viewer receives the cloud manifest through its public optional
`pointCloud` input. App routes serve immutable manifest/chunk resources; the
existing buffered videos contain rendered STL silhouettes in both cameras.
Source PNGs are retained for inspection but are not fetched during playback.

## Authored geometry overlays

Targets can reference a hash-bound `authored_geometry` manifest. It identifies the exact ordered keypoints and connection topology, the matching STL hash, an original-mesh millimeter origin, and a dense binary outline asset. Authored point coordinates remain in original STL millimeters; conversion to source mesh units and the Forge segment frame is explicit. The same point array supplies the 3D landmarks and camera projections.

The recovered outline projector retains the original crease/silhouette edge selection and BVH self-visibility tolerances. Preparation runs it through Node on the current fitted poses, streams one projection at a time, and encodes thin cyan mesh lines with contrasting magenta keypoints into a new annotated video revision. Filled points are mesh-self-visible; hollow points are self-occluded. External occlusion is unknown. These are pose-projected authored points, not detector predictions or accepted training labels. Raw images, fits, gate results and prior playback revisions remain unchanged. Node and ffmpeg must be available for this preparation step.

The dense outline container begins with a little-endian uint32 JSON header length; header entries give typed-array constructor, byte offset and element count. Payload starts at an eight-byte boundary; arrays preserve the original vertex/triangle/edge/BVH ordering. Project files contain data rather than executable JavaScript. The generic projector code is versioned with the application.

Playback verification distinguishes cloud loading/cache misses from unavailable presentation clocks. Readiness means the short cloud clip is resident; it does not by itself prove synchronized video presentation. The test harness checks that replay and seeks issue no cloud requests after readiness and reports each hiding reason separately.

For the current Benchy review fixture, run `node tools/verify_presentation.mjs` with the source backend on port 8006 and the UI on port 5176, then `backend/.venv/Scripts/python.exe -B tools/check_presentation_pixels.py`. The headless check captures the actual displayed canvases and an independent browser decoder at identical dimensions, with normal browser security intact. It covers raw/annotated views, both cameras, local frames 0/375/600/650/749 and cache reuse across media choice and seeks. Results and screenshots stay under ignored `.test-artifacts/`.

The native sustained harness is `skellyclicker-ui/tests/reconstruction-playback.mjs --sustained`; use `SKELLYCLICKER_TEST_CDP_PORT` only for a task-owned native review window. Without it, tests use headless Edge and discover the backend from the existing native window, or use `SKELLYCLICKER_TEST_BACKEND_URL`. Capture comparisons count actual committed image pairs and source frame identities, not requested seek times.
