# Image training set control panel

The sidebar action opens the full workflow definition for the current project:
source inputs → synchronized images/calibration → stereo 3D → STL poses →
projected candidates → human review/correction → approved dataset publication.
The prepared-data bind/choose/project/publish pipeline is the candidate stage's
subgraph, not the full workflow.

This slice configures and inspects the workflow. It does not execute the new
stages, correct labels, publish a dataset, or start training. The run action is
disabled. Existing preparation remains a separate explicit action. Stage badges
distinguish linked inputs, reusable artifacts, manual gates and missing capabilities.
Presence of an artifact is not a fresh hash verification or human approval.

## Shared UI provenance

All controls below are public `@freemocap/ui` imports. Core was read only.

| Core source in `freemocap-ui/src/` | SDK public surface | SkellyClicker consumer |
| --- | --- | --- |
| `layout/content/SidePanelContent.tsx` → `components/control-panels/recording-info-panel/ProcessMocapPanel.tsx` → `ButtonSm` + `styles/button-sm.css` | `SidebarProcessingAction` with Core primary/accent classes and processing icon | `main.tsx` sidebar |
| `components/mocap-setup/mocap-setup-modal.tsx`, `mocap-processing.css` | `PipelineWindow`, `PipelinePanel` | `TrainingSetPanel.tsx` |
| `components/mocap-setup/processing-outline.tsx`, `stage-section.tsx` | Shared left outline and section hierarchy within `PipelinePanel` | App stage metadata and controlled configuration |
| `components/common/settings-layout/setting-row.tsx`, `setting-select-input.tsx`, `setting-toggle-switch.tsx`, `settings-summary-chip.tsx`, `settings-layout.css` | `SettingRow`, `SettingSelectInput`, `SettingToggleSwitch`, `SettingsSummaryChip` | The same form content in list and graph nodes |
| `components/ui-components/ValueSelector.tsx`, `AnchoredInfo.tsx` and floating tooltip helpers | `ValueSelector`, `AnchoredInfo` | Numeric controls and explanations hidden behind info buttons |
| `components/processing-graph/ProcessingGraphView.tsx`, layout and explanation machinery | SDK graph renderer | Typed artifact ports/edges from `training-workflow.ts` |

The graph opens in two rows at a readable scale; explicit Fit all is an overview.
All settings start expanded. Each stage has an independent chevron disclosure;
toggling it preserves the camera transform exactly. Stage titles and control text
wrap fully. The outline and magnifier focus a stage independently of disclosure.
The list uses the same settings, open state and left outline. Explanatory prose, hashes and provenance are
in info surfaces; only labels, values, concise status and actual errors remain
visible by default. SDK provenance records extraction and adaptations.

## Data and configuration

The existing project and `/api/preparation/result` responses supply the source,
target, prepared range, source frame count and calibration. Fixture counts and
52-point geometry are not hardcoded into the component. Existing adapter constants
are read-only controls; their help describes their limitations, including the
recording-specific mask initializer. General arbitrary-STL initialization remains
upstream work.

A browser-local draft is keyed by project UUID and bound to source/target hashes
and result pointers. It is configuration only, not a saved label dataset. A changed
binding resets the draft. Storage errors are visible. Sampling uses source range,
fit filter, stride, then optional cap; both camera images remain one moment.

## Verification

From `skellyclicker-ui/`:

- `npm run build`: TypeScript and production bundle.
- `node --test tests/training-workflow.test.mjs`: source identities, deterministic
  sampling/filter order, validation and graph dependencies including the review gate.
- `node tests/native-training-panel.mjs`: operates the existing native window on
  CDP 9224; no second visible window or processing run. Uses the current Benchy
  project as an acceptance fixture, changes its browser configuration draft,
  checks both views, info/keyboard, pan/zoom, range errors and reopening, and leaves
  the panel open. Screenshots/report go to ignored `.test-artifacts/`.

`node tests/native-training-disclosure.mjs` checks initially open settings, full
wrapped titles, pointer/keyboard disclosure without camera movement, state across
views/focus, measured port anchors and two-row separation in the existing window.

Native testing uses the fixture's source 90–840 range and restores valid settings
with stride 30, no cap and all fit statuses. This is test setup, not a product default.

## Canonical target inputs

New projects copy the selected STL into `recordings/<recording-id>/skellyclicker/inputs/targets/<object-id>/<revision>/<object-id>.stl`, constructed through the SDK RecordingStructure application extension. The neighboring named target manifest uses `path_basis: target_directory`; its geometry and authored definition references remain relative to that directory. Project catalogs select this manifest. The app normalizes references only in memory for its existing project consumers. Opening a project reads its selected target automatically; Browse is an explicit replacement draft, not an obligatory input step. New-project fields prefill from the open project's actual recording, calibration, target and units; no Benchy source paths are hardcoded.

`target_snapshot.canonicalize_target` explicitly copies and verifies an existing library target into this recording-local location, preserves original/library bytes, and updates the catalog last under the project lock. Authored keypoints and outline bytes retain their hashes; the authored manifest changes only to use local paths. A retained update record contains the previous project manifest and source provenance. Reads never relocate data implicitly.

Validation: `python -B -m unittest discover -s backend/tests` covers new-project placement, automatic selection, explicit correction, same-mesh/unit identity, authored points, unchanged originals and relocation. Native OS Browse/Cancel remains unverified because computer-use access to SkellyClicker was denied.

## Executable prepared-data slice

| Stage | Existing interface and owner | Behavior in this slice |
| --- | --- | --- |
| Bind inputs | SDK storage identities/relative paths; APP Project/Target and canonical recording extension | Validate source, pose/timing/calibration, STL units, ordered authored points and cached projection identities. |
| Choose moments | APP configuration semantics; Arrow tables from existing preparation | Range, fit filter, ordered stride, then cap; preserve exact int64 timestamps and stereo grouping. |
| Project labels | APP load_authored_geometry/camera_projections and existing project_authored_geometry Three.js worker | Reuse only hash-bound projections of the same geometry, poses and calibration; retain invalid/occluded rows explicitly. |
| Publish candidates | SDK project_lock/publish_directory/atomic_json/inventory | Publish immutable unreviewed Parquet artifacts and update the APP selection pointer last. |
| Run/status/cancel | SDK compiled graph, synchronous PipelineRun, registry/router and snapshot forwarding | Execute inside the existing APP job lifetime; one shared admission gate with preparation; stream retained full snapshots through the existing connection. |
| Result review selection | SDK confirmed presented-frame and seek handle; APP revisioned selection | Select exact published moments, never infer source identity from displayed counters. Selection is not approval. |

SkellyForge already supplies rigid STL model construction, rotation and coordinate conventions through normal installed imports in playback_adapter and recording_layout. The first prepared-data run needs no new SkellyCam/SkellyTracker dependency, capture, detector, depth or pose execution. Their independently owned capabilities remain available for later fresh-input stages. No Core runtime dependency or subrepository branch change is introduced.

## Candidate execution and review

The panel now offers Preview candidates and Generate candidates for compatible prepared inputs. Preview is read-only. During execution, the existing graph/list panel shows the four actual SDK operations; Workflow settings returns to the full workflow. Run cancellation is cooperative, and publication checks cancellation immediately before its atomic commit. A successful committed publication remains successful if cancellation arrives afterward.

The app shares its admission lock and job catalog with preparation. SDK PipelineRun.execute schedules graph operations inside the admitted APP job thread. The existing WebSocket forwards full retained pipeline_snapshot messages through the SDK forwarder; the client subscribes through TransportService and retains sequence ordering per run. HTTP status is for inspection/recovery, not progress polling. Backend restart does not resume interrupted work; request/status files remain in the recording's working/labels directory.

Routes: POST /api/labels/preview; POST /api/labels/runs; SDK GET /api/label-tasks and GET/POST /api/label-tasks/{run_id}[/cancel]; GET /api/labels/runs/{run_id}/result; GET /api/labels/result; GET/POST /api/labels/selection. Stale input or competing mutations return409; invalid configuration returns422. Earlier run result endpoints retain their own result identity after later runs.

Saved candidates live under recording/skellyclicker/labels/<run-id>/r001 with moments.parquet, images.parquet, labels.parquet and manifest.json. Images reference the verified original prepared PNGs; no annotated overlays become training images. Every label retains ordered keypoint index, native pixel coordinates, projection validity, in-bounds status, mesh self-visibility and unknown external occlusion. Exact nanoseconds stay int64 in Parquet and strings in JSON. Manifest identities bind source, poses, calibration, target, ordered definition, projection bytes, configuration, executable recipe bytecode and available package versions. Missing bundled distribution metadata is explicitly null.

Generated candidate review uses PlaybackWorkspace controlsRef/onPresentedFrame. Navigation awaits the actual synchronized pair; selection reads getPresentedFrame again at the action boundary. The app checks that recording/source frame against the published moments, whose exact timestamp is sent to the server. Each selection write creates a retained review revision and checks expected result/selection identities under the project lock. Included images remain unreviewed. Rigid-pose correction, keypoint editing, human approval, approved-dataset publication and training are not implemented by this slice.

Verification: backend/tests/test_labels.py covers success, failure, cancellation, competing runs, stale writes, retained two-run results and selection persistence. tests/native-label-generation.mjs runs the actual prepared fixture through the native controls and reloads the saved selection. tests/reconstruction-playback.mjs --sustained uses the existing app when SKELLYCLICKER_TEST_CDP_PORT=9224 and checks paired playback, cloud/model alignment, loops and seeks.

## Synchronized target close-ups

Playback opens on annotated media when available; Raw remains a session choice. The SDK owns the outlined selector and the close-up canvas, which draws from the same committed bitmap as the full camera view. The larger floating inset can be moved and resized within its camera view; a protected top strip keeps image controls accessible. There is no second player, decoder, clock, or per-frame request.

The APP supplies `PlaybackWorkspace.getTargetCrop` through `useTargetCrop`. It loads compact metadata once from the registered playback's target-crops endpoint. Bounds derive from the existing hash-verified dense projected outline and ordered points, with 3% padding (at least 3 pixels for overlay strokes) and image clipping. Missing, nonfinite, behind-camera and wholly off-image projections are unavailable; they never reuse a prior frame's crop. The provider checks recording identity, exact media filename, published source frame and image dimensions. Raw and Annotated use the same geometry bounds. The backend streams the dense cache into a bounded four-entry compact cache; no fitting or media generation is performed.

`backend/tests/test_target_crops.py` tests edge clipping and unavailable projections. `tests/native-target-crops.mjs` checks native Annotated default, source 90/120 and other seeks, mode changes, zoom, playback and loop frame/epoch equality. Evidence lives under ignored `.test-artifacts/target-closeups-native.*`.

## Image inclusion and included-frame navigation

The Images sidebar is now the default when generated results exist. Project switches back to source/project controls. The SDK ImageCatalog displays every generated image in stereo-moment groups, with lazy thumbnails, camera/time identity, selected state, All/Included/Excluded and camera filters. On-image ImageSelectionToggle controls use the actual camera-specific committed presentation and verify its epoch again at the action boundary. A noncandidate playback frame shows No generated labels. No frame polling is introduced.

Included frames navigation uses saved per-camera membership. Both cameras deduplicates moments with at least one included image; a camera filter scopes membership to that camera. Previous/Next pause and await the confirmed paired presentation. F/G work only with focus inside the browser, and boundaries do not wrap. All generated explicitly switches to candidate navigation.

Selection schema version 2 stores image_id, camera_id, moment_id, source_frame and exact int64 timestamp_ns. Existing version 1 pair selections expand to both published images on read; the next edit publishes a new versioned review without modifying the old one. Each write uses the existing result and selection hash checks. Inclusion is a draft choice, not human approval or a published training dataset.

The SDK close-up is now a larger floating 640-pixel canvas with independent drag and resize handles, pointer capture, keyboard arrows, per-camera layout retention and parent bounds. A protected top control strip prevents overlap with image inclusion. Both full view and close-up use the same committed bitmap. tests/native-target-crop-interactions.mjs verifies paused/live interaction, source switching and parent resizing; tests/native-image-selection.mjs verifies independent membership, included/camera-filtered navigation, focused shortcuts, persistence, noncandidate handling and save failures.

## Review-first workflow

A newly generated batch publishes an initial all-included image review together with its label-result pointer. Opening or rendering a batch never initializes over an existing selection. Existing batches offer an explicit styled Include all action, which writes a retained review revision with the same stale-input and selection guards. The workflow is generate, review labeled/included moments, then exclude unwanted images; inclusion remains distinct from label approval.

The playback toolbar contains separate Labeled and Included previous/next groups. Both navigate the actual source timeline through confirmed SDK seeks; Included uses saved membership and the browser camera filter. Duplicate sidebar stepping controls are removed. The browser shows tightly cropped target PNGs with the actual cyan mesh wireframe and magenta ordered keypoints, using verified projection offsets and original frame bytes. Lossless thumbnails preserve thin outline colors; unavailable projections show an explicit placeholder. No full-scene fallback is substituted for a missing target.

Full camera images align to the top of their panes. Headerless close-ups initially sit at the bottom, use the target bounds' aspect ratio without added letterboxing, and retain independent manual placement. Drag the image itself; resize from any of four edges or corners. The log panel can collapse to zero via its divider or control, and its restore button remains reachable while logging continues.

`tests/native-review-workflow.mjs` checks log collapse/restore, real crop resources, toolbar navigation, headerless dragging and all eight resize handles. The check temporarily includes one image for navigation and restores the fixture's existing exclusions. Backend tests verify new-batch inclusion, preserved exclusions, explicit Include all, revision migration, and exact outline/keypoint pixels in thumbnails.
