# Session restoration

SkellyClicker saves successful project opens and navigation changes immediately in
`%LOCALAPPDATA%/SkellyClicker/session.json` on Windows. Other platforms use
`~/.config/SkellyClicker/session.json`; `SKELLYCLICKER_SESSION_PATH` can override
this location for isolated tests. The APP owns this schema and uses the SDK's
atomic JSON writer (flush, fsync, same-directory replacement).

The session contains the last project manifest, selected recording, Viewer or
Training dashboard tab, sidebar mode and selected saved training run. Project
manifests remain authoritative for label membership and existing processing
results. Restoring a session does not edit those manifests, start training,
resume an interrupted job or start playback. Annotated playback keeps its
existing default.

Startup checks backend readiness before reading the session and opening its
project. A prior browser-local project path is migrated only when there is no
saved disk project. An unavailable project produces a visible error with Retry
and project-open controls; its saved path is retained. Project opens update the
session only after validation succeeds. Same-project refreshes preserve recording
and run choices. Navigation updates carry the project path so delayed updates
from an old project are rejected. Browser writes are serialized.

Recording selection currently restores the existing recording-browser choice;
the existing playback result remains project-owned. This does not add a new
multi-recording processing or playback workflow.
