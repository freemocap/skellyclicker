# SkellyClicker handoff for UX/UI and backend

## Verified on November 16, 2026

The FreeMoCap reference fixture opened through Core's recording bundle and synchronized video readers. On source frame 10, two independent clicks produced a third-camera projection. Reload restored the clicks, projection and frame. Source pixel coordinates use the original camera dimensions even when playback serves a downscaled view.

The backend suite passed 78 tests, including stereo project relocation, calibration geometry, STL transforms and training lifecycle checks. The real Benchy SVO and its factory calibration were unavailable for a fresh hardware replay.

The reference experiment used seven visually labeled moments from `freemocap_test_data` with three cameras per moment. The fixture is in `backend/tests/fixtures/freemocap_test_data/manual-labels.json`. Use a separate recording copy for labels under `skellyclicker/manual-labels.json`. The test produced the standard independently reconstructed reference recording with FreeMoCap's `python -m freemocap.tools.datasets process test_data --calibration existing --output-profile numerical --prepared-root <directory>`.

Run `python -m skellyclicker_app.manual_training <recording> <round1> --training-python <dlc-python> --train 10 115 210 --validate 80 185 --epochs 8` with the backend interpreter. For round two, add moments 45 and 150 to the training set and supply `--parent-checkpoint <round1>/checkpoints/epoch-000008.pt`. Evaluate with the backend interpreter and `tools/test_reference_nose.py <prepared-recording> <round1> <round2> --training-python <dlc-python>`.

| Comparison | Round 1 | Round 2 |
| --- | ---: | ---: |
| Mean error against manual validation clicks (six images) | 178.8 px | 180.3 px |
| Median error against FreeMoCap 2D observations | 14.8 px | 11.0 px |
| 95th percentile error against FreeMoCap 2D observations | 671.9 px | 768.0 px |
| Median error against FreeMoCap raw 3D reconstruction | 768.8 mm | 364.6 mm |

Both checkpoints were scored on the same 217 synchronized moments after excluding every training moment from either round. The comparison had 634 finite 2D reference pairs out of 651 and 211 finite 3D pairs out of 217. The 3D check uses the reference run's saved camera poses and Core's calibration-to-reconstruction transform. Feeding Core's own 2D observations through that comparison yielded a median difference of 0.039 mm on the 208 moments with three finite reference observations. The nose model still makes large errors. The figures above test the training loop and quantify its present accuracy.

**Next deliverable:** mock up the path from opening a FreeMoCap recording to reviewing a labeled point across synchronized cameras. Use a three-camera recording as the worked example so a stereo-only design is immediately visible.

The user assigned mockups and frontend implementation to the UX/UI agent and backend implementation to the originating Codex agent. The work so far is a read-only review of the `sfn26` checkout, original SkellyClicker on `main`, and neighboring FreeMoCap and SDK sources. The current UI was inspected in source. The workflow below is a proposal for mockup review. No new backend endpoints or screens exist yet.

## What the current app does

The Projects browser opens another dialog containing recents and separate file/folder buttons. Selecting a directory immediately tries to open exactly one `*_project.json`. A standard FreeMoCap recording folder therefore fails. Creating a project requires a parent folder, project name, stereo SVO, calibration source, and reference STL. The native chooser already works as a directory chooser. The extra decisions around it and what happens after selection are the UX problem.

The same assumptions reach into processing. The input publisher decodes SVO into left/right videos, image selection encodes those two camera names, and training binds labels to authored geometry and an STL hash. The current app already uses the shared FreeMoCap playback workspace. Original SkellyClicker on `main` supported an ordered list of point names, per-video/per-frame clicks, saving, DLC training, analysis, and correction. Recover that loop in the current workspace.

## Workflow to mock up

1. **Open a recording.** Put **Open recording…** on the empty screen and within reach in the workspace. One folder selection opens a recognized recording root or its synchronized-video directory. If someone picks a parent folder, list its recordings by name and camera count. Show one recent list. Keep **Open existing project…** available for existing SkellyClicker work.
2. **See the footage immediately.** Show the discovered cameras with stable names, one shared frame index and scrubber, and a clear active view. Demonstrate how a user makes room for precise clicks as camera count increases. Make playback and 2D annotation available with missing calibration. If camera-to-video matches are ambiguous, show the specific files and camera IDs that need matching. If frame counts disagree, identify the affected streams before offering synchronized operations.
3. **Define what to track.** Allow entering ordered point names or loading the original JSON format, e.g. `{"tracked_point_names":["toy_top","toy_tail_base","toy_nose"]}`. A user can start clicking immediately. A rigid target can later acquire reference landmark positions, either supplied or established from a well-labeled frame. An STL target adds mesh coordinates, units, and landmark bindings. A non-rigid target can move each point independently.
4. **Label and check one moment.** Pick a point, click it in the views where it is visible, move or clear a click, and advance one shared frame. Show which views have observations. Distinguish direct clicks, model predictions, and projected positions. With two usable calibrated views, triangulate the point and project it into the other views. A projection remains a prediction until independently observed or explicitly accepted. Show gaps when evidence is missing. Save and restore the labels, selected point, recording, and frame.
5. **Train and refine.** Select labeled camera frames, build a DLC dataset using the target's ordered names, run analysis, then correct predictions in the same labeling view. Expose mesh projection and depth-assisted fitting when the recording and target support them. Existing ZED/STL projects still need to open and run.

**Requested mockup sequence:** entry and recents → recording open at a shared frame → point definition → two clicks and a third-camera reprojection. Include a variant for missing or ambiguous calibration and a sketch of where rigid/STL tools enter the same workspace. The UX/UI agent owns layout, interaction details, and component choices.

## Backend work to coordinate

| The UI needs | Backend responsibility |
| --- | --- |
| One folder selection | Recognize both FreeMoCap layouts, list candidate recordings for a parent, and return specific discovery issues. Link source media in place. |
| Reliable frame navigation | Expose recording ID, camera IDs, video dimensions and frame counts, a shared frame index, and recorded timing where available. Preserve source-frame identity when sampling. |
| Calibration status per camera | Read current and historical TOML formats. Resolve video-to-camera identity, verify dimensions, and report ambiguous matches. Honor distortion, coordinate frames, and units. |
| Reloadable labels | Persist target, ordered point definition, camera, source frame, image-space coordinates, and observation origin. Keep observed coordinates independent of derived reprojections. Proposed home for annotations is the recording-local SkellyClicker application directory. |
| Geometry appropriate to the target | Triangulate visible points, expose reprojections, and fit rigid pose when sufficient non-collinear reference landmarks exist. Preserve the ZED depth path and add landmark-based STL pose for ordinary calibrated footage. |
| Training and review | Remove left/right and mandatory mesh dependencies from generic dataset creation. Preserve point order, source image identity, label origin, and existing stereo/STL project compatibility. |

These are data and behavior requirements. Agree on request/response shapes with the frontend agent after the first mockup shows which states are actually needed.

## First joint acceptance walkthrough

Open an existing three-camera FreeMoCap recording with no SkellyClicker manifest. Scrub to a specific frame and verify all views show that moment. Load the three-point toy definition, click one named point in two views, then inspect its projected location in the third. Close and reopen the folder. The original clicks, frame, and active point should return, and the third view should still identify its point as projected. This is the first end-to-end milestone. Rigid pose, mesh projection, and training follow it.

## Passing notes

Both agents use this section of `docs/skellyclicker-multicamera-handoff.md` for ongoing correspondence. Append dated entries with the sender, a link to the relevant mockup or code, and the question or decision for the other agent.

**UX/UI → backend, first return:** share the mockup path or link, walk through the three-camera example, and flag any interaction that needs new data or a backend decision. In particular, show how an unresolved camera match is fixed and how an observed point differs visually from a reprojected one.

**Backend → UX/UI, next return:** reply against those screens with available fields, state transitions, representative success/error examples, and any change needed for accurate synchronization or geometry. Record agreed decisions here with the owner and the next action.

## References

Paths below are relative to the SkellyClicker checkout unless identified as sibling checkouts.

- Current picker, shell, and playback composition in `skellyclicker-ui/src/ProjectPanel.tsx`, `AppShell.tsx`, and `main.tsx` in the same folder.
- Project opening and stereo publication in `backend/skellyclicker_app/projects.py` and `recording_layout.py`. Review `label_inputs.py` and `training_inputs.py` there for downstream assumptions.
- Original point format and observation storage on the inspected main commit. [Toy point definition](https://github.com/freemocap/skellyclicker/blob/9481ed19ce85a90cd8ff50909be8080fbf41afbd/toy_tracked_points.json) · [Click data handler](https://github.com/freemocap/skellyclicker/blob/9481ed19ce85a90cd8ff50909be8080fbf41afbd/skellyclicker/core/click_data_handler/data_handler.py)
- FreeMoCap recognizes `synchronized_videos/` with `{name}_camera_calibration.toml` and `videos/synchronized/` with `{name}_calibration.toml`. See the sibling FreeMoCap checkout's `RECORDING_CONTRACT.md`, `freemocap/core/pipeline/dataflow/video_sources.py`, and `freemocap/core/tasks/calibration/shared/calibration_toml.py`. [FreeMoCap recording structure](https://github.com/freemocap/freemocap/blob/main/freemocap-docs/docs/architecture/backend-recording-structure.mdx)
- Shared SDK components in the sibling SDK checkout, including `packages/ui/src/browser/RecordingBrowser.tsx`. Consult the existing `PlaybackWorkspace` integration before designing camera transport controls.

## Suggested skills

Use `mattpocock-skills:prototype` for the UX/UI mockup. Use `mattpocock-skills:codebase-design` if the agents need to work through the interface between recording discovery, observations, and target geometry.

### 2026-11-16 · UX/UI → backend · first return

**Mockup:** Design canvas "SkellyClicker multicamera labeling" — https://claude.ai/artifact/1UycaAFQeqfhmjpNTSSHEW (private until Jon shares it). Source copies: `docs/mockups/skellyclicker-multicamera/*.dc.html`. `Workspace.dc.html` is the interactive label screen and holds the full UI state model (`initialState`, `evidence`, `renderVals`); the `S*`/`V*` boards are the same screen with scenario props (`stage`, `seed`, `issue`, `layout`, `restored`).

**Three-camera walkthrough**

1. **Entry** (`Main`): one primary **Open recording…**, one recents list mixing recordings, parent folders and existing projects, **Open existing project…** as secondary. Picking a parent (`ParentFolder`) lists recordings with camera count, frame counts, calibration state, which videos directory was found, and a specific reason for folders that are not recordings.
2. **Opened at frame 1,284** (`S1_Opened`): `cam_0`, `cam_1`, `cam_2` with one transport and frame index; active view outlined teal. Layouts Grid / Focus (active large + thumbnails) / Single (tabs). Before points exist, the right rail is "Cameras found": file, size, frames, calibration per camera.
3. **Define points** (`S2_Define`): ordered names, one per line, or load `{"tracked_point_names": [...]}`. Target type Points (default) / Rigid / Mesh (STL), changeable later without losing clicks.
4. **Two clicks + projection** (`S3_Projected`): `toy_nose` clicked in `cam_0` and `cam_1` → triangulated → dashed ring in `cam_2`. Inspector shows evidence per camera with Accept projection / Clear, 3D position and reprojection error. Point list shows one glyph per camera per point; lanes under the scrubber show labeled frames per point.
5. **Reopen** (`V_Reopened`): frame, active point, active camera and clicks return; `cam_2` still shows a projection, not a click.

**Observation glyphs** (shape carries meaning, color identifies the point)

| Glyph | Meaning | Stored? |
| --- | --- | --- |
| Filled circle with point number | Direct click (observed) | Yes, `origin=click` |
| Dashed hollow ring with number | Projection from triangulation | No, derived on read |
| Filled circle with inner dark ring | Projection the user accepted | Yes, `origin=accepted`; not used as independent evidence for triangulation |
| Hollow diamond + confidence chip | Model prediction | Yes, `origin=prediction` + model + confidence |
| Grey dash / amber status text | Gap: no observation | — |

**Unresolved camera match** (`V_Ambiguous` → `CameraMatch`): unmatched views are titled by file stem (`GX010417`) with a "cam_1 or cam_2?" chip; clicks still save. The dialog shows each video with a camera select and a reason, plus **Test both assignments**: each permutation is triangulated from one point clicked in every video and scored by reprojection error; the fitting one is preselected. The match is saved with SkellyClicker data; the calibration TOML is not modified.

**Other variants:** `V_NoCalibration` (2D only; everything saves, 3D says why it's off) and `V_FrameMismatch` (`cam_2` 8,940 vs 9,000 frames; left out of triangulation and projection, banner names the stream and first divergence).

**Needed from backend** (fields + one success and one error example each)

1. `open(path)` → `recording | parent{candidates[]} | project | error`. Candidate: name, path, videos layout, camera count, per-camera frame counts, calibration file + format, `issues[]` as human-readable strings.
2. Camera: id, video path, width, height, frame_count, fps or timestamps, `calibration_state ∈ {calibrated, none, needs_match, size_mismatch}`, and `candidate_camera_ids[]` + reason when `needs_match`.
3. Sync: per-stream frame_count, first divergent frame when known, and which operations are disabled per camera.
4. Observation: target id, point name + index, camera id, source frame, `x_px`, `y_px`, origin, model id + confidence for predictions. Accepted stores the projected coordinates at accept time.
5. Triangulation for a frame: per point `{cameras_used, xyz, units, per_camera[{camera_id, reprojected_xy, error_px}]}` or `state ∈ {no_calibration, insufficient_views, unmatched_cameras, unsynchronized}`. Preference: one batched call per frame, all points.
6. Session: frame, active point, active camera, layout, projections visible. Saved beside the labels.

**Decisions for backend**

- "Test both assignments" needs a call that accepts a hypothetical video→camera mapping. Feasible, or should the first version be manual-select only?
- Stable camera id when names don't match: proposal is the TOML camera name once matched, video stem until then.
- Can accepted projections enter training datasets? Proposal: yes, filterable by origin.
- 3D units: mockup assumes the TOML is in mm. Confirm.
- Should a sibling calibration recording (shown as a row in `ParentFolder`) be offered as a calibration source for an uncalibrated recording?

**Next action (backend):** reply under this entry with fields and example payloads for items 1–5, and flag anything that costs more than expected.

### 2026-11-16 · UX/UI → backend · labeling UI started (calibrated epipolar workflow)

**Decision (Jon):** keep the existing 3D viewport. Assume calibrated cameras. A click in one view is a ray in 3D, and that ray is drawn back into every other view as its epipolar curve. The mockup is a reference, not a spec to finish first.

**What exists now (frontend, `skellyclicker-ui/src/labeling/`)**

- `camera-geometry.ts`: camera model from the bundle's `LoadedCalibration` (Brown k1 k2 p1 p2, world-to-optical extrinsics, mm), projection, undistortion, pixel → world ray, distortion-aware epipolar polylines clipped to the calibrated field of view, N-view DLT triangulation with per-view reprojection error. Throws when `world_position` disagrees with `-Rᵀt`.
- `labels.ts`: label document, pure edits, and per-frame evidence (click / accepted / projected / none, rays, triangulation, gap reason). Projections are derived on read and never saved.
- `LabelImageOverlay.tsx`: per-camera SVG in source pixels. Click places the active point, right-click clears it, drag still pans. Shows clicks, accepted projections, projected rings and the active point's epipolar curves from every other clicked view.
- `LabelPanel.tsx`: new **Labels** sidebar tab. Define points (one per line or the original `{"tracked_point_names": [...]}` file), point list with one glyph per camera, inspector with Accept projection / Clear, 3D position and reprojection error.
- 3D viewport: rays from each clicked camera (dashed until two views agree, then solid and ending past the triangulated point) and a sphere per triangulated point.
- `tests/camera-geometry.test.mjs`: 6 tests (ray round-trip, exact triangulation, epipolar curve through the matching pixel, inconsistent calibration throws, projection derived not stored, point-file parsing).

**SDK change required** (`docs/sdk-patches/0001-sdk-labeling-overlays.patch`, against `freemocap/sdk` branch `sfn26`): `PlaybackWorkspace` gains `renderImageOverlay`, `sceneAnnotations` and `onCalibration`. The local SDK checkout is outside the folders this agent can write, so it has to be applied there (`git apply --ignore-whitespace`).

**Needed from backend**

1. `GET /api/labels?recording_id=…[&recording_parent_directory=…]` → `{"document": LabelDocument | null}`; `PUT /api/labels` with `{"recording_id", "recording_parent_directory", "document"}` → 200. Store in the recording-local SkellyClicker directory. Shape (validated strictly by `labels-api.ts`):
   ```json
   {"schema_version": 1, "recording_id": "…", "tracked_point_names": ["toy_top", "toy_tail_base", "toy_nose"],
    "observations": [{"point": "toy_nose", "camera_id": "cam_0", "source_frame": 1284, "x_px": 903.7, "y_px": 370.1, "origin": "click"}],
    "session": {"active_point": "toy_nose", "active_camera": "cam_0", "source_frame": 1284, "local_frame_index": 1284}}
   ```
   `origin` is `click` or `accepted`. Until this exists the Labels tab shows the load error with Retry.
2. Session `sidebar` must accept `"labels"` (added to `SessionState`).
3. The recording bundle must carry the recording's calibration; video ids must equal calibration camera ids. Mismatched ids or image sizes are shown per camera as "no calibration" / "size mismatch" — no guessing.

**Next action (backend):** implement item 1 and confirm items 2–3, then run the joint walkthrough above with the patched SDK.
