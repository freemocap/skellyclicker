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
| `components/common/settings-layout/setting-row.tsx`, `setting-select-input.tsx`, `setting-toggle-switch.tsx`, `settings-summary-chip.tsx`, `settings-layout.css` | `SettingRow`, `SettingSelectInput`, `SettingToggleSwitch`, `SettingsSummaryChip` | The same form content in list and focused graph nodes |
| `components/ui-components/ValueSelector.tsx`, `AnchoredInfo.tsx` and floating tooltip helpers | `ValueSelector`, `AnchoredInfo` | Numeric controls and explanations hidden behind info buttons |
| `components/processing-graph/ProcessingGraphView.tsx`, layout and explanation machinery | SDK graph renderer | Typed artifact ports/edges from `training-workflow.ts` |

The graph opens in two rows at a readable scale; explicit Fit all is an overview.
The outline focuses a stage, and its shared settings expand there. The list uses
the same settings and left outline. Explanatory prose, hashes and provenance are
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

Native testing uses the fixture's source 90–840 range and restores valid settings
with stride 30, no cap and all fit statuses. This is test setup, not a product default.
