# Viewer restoration audit

The historical references below cover the legacy Python viewer, the project-based desktop at `92f48ff`, and the opened-folder path introduced in `87e8ae4`. The checks apply to a synchronized recording opened directly from its folder. A green project-dashboard test alone cannot establish that this path works.

## Restored and exercised

- The Training tab indicates an active run from the Viewer. The Training workspace shows preparation, elapsed time, epoch progress, loss and validation error curves, and saved checkpoint samples. The browser regression replays preparation and measured epochs and reloads a completed run. See `skellyclicker-ui/tests/keypoint-training-feedback.mjs`.
- The Training set tab shows the current clicked camera images used to form the next training and validation sets. Each image has a full-frame view and label-centered crop. Camera and source-frame identity are preserved.
- Dragging a clicked point in either Training set view uses the Viewer marker gesture. The browser check verifies both source coordinates on disk, the other observations, and the marker position after reload.
- The Viewer scrubber includes two frame-aligned quality tracks. The upper track shows the mean human-label reprojection error across triangulated clicks. The lower track shows the mean pixel distance from saved model predictions to matching clicks. Colors run from green at zero through yellow at six pixels to red at twelve pixels and above. Gray identifies observations without a measurable error. Empty positions have no observations for that track.
- Active training displays a rotating pink perimeter around the Training tab. The original SDK training stage panel shows operation states, elapsed times, and progress counts above the plots. The default list fits the stages across the results area, with Graph available for inspecting the pipeline.
- The opened-folder Viewer displays source-aligned labels and saved model predictions in the full frame and target close-up. The manual-labeling close-up stays in place during a drag. The Viewer-controls change verified that dragging a marker updates its source-pixel coordinates while the close-up stays put. The recording browser check covers crop pixels and the prediction layer using synchronized videos and a saved worker predictions file. See `skellyclicker-ui/tests/recording-review.mjs`.

## Historical evidence

| Capability | Evidence |
| --- | --- |
| Machine labels and point names | The Python viewer handles `m` for machine-label visibility, `n` for names, and `v` for copying predictions into human labels. See `old/skellyclicker/core/video_handler/video_viewer.py` and `image_annotator.py`. Visibility and writing labels were separate actions. |
| Raw and annotated playback | The project viewer offered a source selector. Annotated frames included projected keypoints and mesh outlines. The full image and close-up used the same committed bitmap and source identity. See `docs/training-set-panel.md` under “Synchronized target close-ups” and `PLAYBACK.md` under “Authored geometry overlays”. |
| Moving and resizing the historical project close-up | The project viewer supported dragging the per-camera close-up, edge and corner resizing, and keyboard adjustment. The historical interaction checks are `skellyclicker-ui/tests/native-target-crop-interactions.mjs` and `native-review-workflow.mjs`. |
| Image inspection | Commits `b2656f6` and `91faa66` expose crop/full framing, annotations, raw-on-hover and full-image inspection. Checkpoint images distinguish frozen labels from saved predictions. See `docs/image-inspection.md` and `skellyclicker-ui/src/CheckpointImages.tsx`. |
| Manual marker editing and guides | At `87e8ae4`, `LabelImageOverlay.tsx` placed or cleared points and drew epipolar curves. Its five-pixel movement threshold rejected a placement after a drag. Accepted and projected observations had distinct ring glyphs. |
| 3D visibility | The SDK viewport has its own scene visibility state. The app also supplies triangulated points and camera rays through `sceneAnnotations`. Project pose candidates, authored geometry and checkpoint predictions have different origins. |

## Independent Viewer controls and editing

These rows track the requested behavior for the Viewer-controls change. Each needs its own interaction check. The historical sources above establish several individual controls but leave the exact old full-frame/crop control matrix unconfirmed.

| Check | Pass condition |
| --- | --- |
| Full-frame visibility | Independently toggle observation markers, epipolar guides, reprojection error and model predictions. Verify each toggle while the other layers are visible. |
| Close-up visibility | Exercise the same four controls in the crop and verify the full-frame settings survive. Check a sparse frame with missing predictions as well as one with measured predictions. |
| Display and edit permissions | Inspect visible observations with editing disabled. Clicking or dragging in that surface must leave the saved observation unchanged. Enable editing for one surface and verify the other surface retains its setting. |
| Marker dragging | Drag a named point in the full frame and crop. Confirm the correct camera, source frame, point and source-pixel coordinates after save/reload. Test with zoom and an off-center crop. |
| Manual-labeling close-up position | Drag the crop background and verify that the panel stays in place. Check that the “Drag image to move” control and tooltip are absent. During a marker drag, verify both the updated source-pixel coordinates and the fixed panel position. |
| 3D visibility | Toggle triangulated points and guides in the 3D view independently of both 2D views. Confirm that camera changes and frame seeks preserve those choices. |
| Duplicate pink ring | On a labeled frame, isolate human labels, projections and model predictions in turn. Confirm one observation glyph per point per surface. Trace any extra ring to its renderer while preserving the intended accepted/projection styles. |
