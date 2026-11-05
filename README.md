# SkellyClicker

The current source is a playback-oriented frontend and a small SDK-backed Python server; Tauri desktop packaging is the next active implementation step. It reuses FreeMoCap's playback components, with SkellyClicker branding and its own backend port.

```text
backend/
  skellyclicker_app/    Current Python server source
  tests/               Lifecycle and image-transport checks
  pyproject.toml       Backend package and SDK dependency
  uv.lock              Backend dependency lock
  .venv/               Local backend environment (ignored)
skellyclicker-ui/
  src/                 Current React frontend and its logo
  tests/               Browser and transport checks
  package.json         Frontend scripts and SDK dependencies
  package-lock.json    Frontend dependency lock
  node_modules/        Local frontend dependencies (ignored)
  dist/                Built frontend (ignored)
old/                   Previous application, preserved only as reference
PLAYBACK.md            Detailed launch, package boundaries and verification
LICENSE                Repository license
```

## Run the current app

First build the SDK packages as described in [PLAYBACK.md](PLAYBACK.md). Then use two terminals from this repository:

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

Open http://127.0.0.1:5176. The backend listens on http://127.0.0.1:8006. Stop each server with Ctrl+C in its terminal.

The verified development shell opens an empty playback workspace with the existing FreeMoCap playback controls and 3D renderer. Loading real recordings, labeling, training and pose editing are subsequent work; they are not implemented by this shell.

## Previous version

Everything specific to the previous version lives in `old/`: Python source, original assets, legacy entry point, package/environment files, point definitions, README and editor snapshot. Its local Python3.10 environment was moved to `old/.venv` and remains ignored. It is preserved as reference, not maintained as a runnable environment after relocation. The new app imports nothing from `old/` and owns a separate copy of the logo it uses. Git metadata and the license remain at the repository root.
