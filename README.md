# SkellyClicker

SkellyClicker is a **Tauri desktop application** with a bundled SDK-backed Python server. Its first slice reproduces FreeMoCap's playback workspace with SkellyClicker branding. The native app owns backend startup, discovers its loopback address after readiness, and shuts it down when the window closes.

Read the [SkellyClicker overview](skellyclicker-docs/docs/intro.mdx) for project terminology and workflow status. The [documentation site README](skellyclicker-docs/README.md) explains how to preview and build the site. Existing [engineering notes](docs/) cover individual features and their verification.

## Repository layout

```text
native/                 Tauri/Rust application, window, icons and installer config
backend/
  skellyclicker_app/     Python server source and app-specific routes
  desktop_entry.py      Bundled backend entry using SDK desktop lifecycle
  tests/                Backend lifecycle and image fixtures
  .venv/                Local development/build environment (ignored)
skellyclicker-ui/
  src/                  React frontend and application-owned logo
  tests/                Browser, native WebView and transport checks
  node_modules/         Local development dependencies (ignored)
  dist/                 Built frontend (ignored)
tools/                  Desktop build/launch wrapper and reference checks
old/                    Previous application, preserved only as reference
PLAYBACK.md             Build, launch, dependency and verification details
```

Native build outputs live in `native/target/`; the bundled backend is generated in `native/binaries/`. Both are ignored. Package manifests and lockfiles belong to their respective source folders.

## Run the built Windows app

Unzip `native/target/release/bundle/portable/SkellyClicker_0.1.0_windows_x64.zip`, then open `SkellyClicker/skellyclicker.exe`. Keep its `backend/` folder beside the executable. Python and npm are bundled/build-time concerns, not runtime commands for users.

An unsigned installer is also built at `native/target/release/bundle/nsis/SkellyClicker_0.1.0_x64-setup.exe`. The portable bundle was launched and checked; the installer itself has not been installed during verification.

## Develop the desktop app

With the sibling FreeMoCap project checkouts and the development toolchain available, run this from the repository root:

```powershell
poe dev
```

The launcher installs locked npm dependencies, builds the SDK client and UI, syncs the Python environment, builds the backend, and starts Tauri. Later runs reuse the backend bundle until backend code, editable Python packages, build inputs, or the bundle itself change. React and Rust watching are enabled.

On Windows and Linux x64, `poe dev` also prepares the pinned DeepLabCut environment and downloads the starting model on first use. Both training modes find that environment automatically. To train a keypoint, open a recording, label it on at least two synchronized frames, and select **Training → Start training**. By default the last labeled frame is held out for validation.

Build the Windows application and installer:

```powershell
node tools/desktop.mjs build
```

## Previous version

Everything specific to the previous version lives in `old/`: source, original assets, entry point, package/environment files, point definitions, README and editor snapshot. The old Python3.10 environment is preserved at `old/.venv` and ignored; relocation does not promise it remains executable. The current app imports nothing from `old/`. Git metadata, license and current repository configuration remain at root.
