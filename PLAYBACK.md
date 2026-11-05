# Playback application (in development)

The new application consumes public SDK packages. The legacy labeling application and its environment remain separate.

Current status: application composition is implemented; SDK playback package integration and launch verification are pending. Do not interpret the empty workspace as verified video playback.

Local development uses the existing `project/repos/sdk` checkout. Build its client and UI packages before the consumer. Frontend dependencies use npm `file:` packages; the isolated backend uses an editable SDK package through uv. No private SDK source aliases are used.

After dependency installation is authorized and the SDK packages are ready:

1. In `backend`, run `uv sync`, then `uv run skellyclicker-playback`.
2. In `skellyclicker-ui`, run `npm install --ignore-scripts`, then `npm run dev`.
3. Open `http://127.0.0.1:5176`.

The backend defaults to `127.0.0.1:8006`. Override it with `--port` or `SKELLYCLICKER_PORT`; configure the frontend's matching endpoint with `VITE_SKELLYCLICKER_BACKEND_URL`. The application binds locally and never terminates another server to claim its port.

The shell mounts the SDK's playback workspace with no recording selected. `/api/status` identifies the backend. `/websocket/connect` sends independently described CBOR `skellyclicker_state` updates, validated through the SDK transport's application-kind registry. Training and labeling are outside this first milestone.
