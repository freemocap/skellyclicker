# Training dashboard and iterative rounds

The Viewer remains mounted when switching to Training dashboard. The SDK owns
pipeline configuration, retained WebSocket snapshots, scalar plots and sample
preview rendering. SkellyClicker owns the dataset, split policy, DLC adapter,
proposal selection and human review.

## Actions and current dataset

Configure training, Start training and Cancel training keep their labels and
positions in the dashboard and configuration panel. Configure is secondary,
Start is primary, and Cancel is a separate danger action. Stage, elapsed time
and actual epoch progress distinguish starting, preparation, training,
evaluation, saving, cancellation and terminal states. Starting is single-flight.
The editable next-run configuration survives panel closure and reload; a running
configuration is read from that run's saved request and is read-only.

Training images are the authoritative persisted dataset members. Removing an
image writes a new selection revision, including its camera identity; Undo writes
another revision. The image and its label rows are absent from future snapshots.
An already-running trainer continues using its immutable frozen inputs. Wider
sidebars add bounded thumbnail columns, and the catalog fills available height
with its own scrolling. Card activation seeks the synchronized viewer.

Generated initial membership is a proposal. The human reviews the images and
removes bad labels; Start training freezes the remaining selection without a
second gate. The snapshot preserves source timestamps as int64 nanoseconds,
stereo moment identity, ordered labels, calibration, STL and image hashes.
Labels retain pose_projection origin independently of human review.

For a new model, validation is the configured temporal tail of selected moments.
A timestamp guard separates it from training; cameras at the same moment share
a split. Guard images remain in the snapshot but do not enter optimization or
evaluation. Continuing from a parent retains its temporal boundary and guard,
so adding examples cannot move its validation tail into training. Validation
membership can expand within that reserved tail; this is not a fixed benchmark.
The small initial fixture verifies plumbing, not generalization quality.

## Checkpoints and continuation

The adapter uses DeepLabCut 3.0.2 / ResNet-50 in an isolated interpreter. Official
dataset creation receives explicit splits, whose saved filenames are verified.
A registered BaseLogger reports actual epoch losses; bounded official train API
calls perform optimization without patching the training loop. Saved checkpoints
are reloaded for previews and validation pixel errors. [@dlcTraining302]

Run data lives under the recording extension's training-runs/<run-id>. Events,
input snapshots, checkpoints and previews retain their actual run/epoch identity.
Cancel writes STOP and checks it at logger/inference boundaries. After 15 seconds
the app terminates its owned worker. Completed checkpoints remain; a partial
interrupted epoch is not promised as saved.

Select a saved run, then choose Starting model or Use recommended checkpoint.
The recommendation is the lowest measured validation mean keypoint error within
that run, not a claim of global generalization. Displayed run and Starting model
are separate choices. Fresh training remains an explicit option.

A continued round copies and verifies the selected checkpoint, preserves its
complete model including the object head, and resets optimizer, scheduler and
round epoch to zero. Exact interrupted optimizer-state resume is not this action.
The installed DLC runner loads the complete model from the snapshot model entry.
Parent identity and the frozen dataset are recorded with the new run. Target,
units, ordered keypoint definition, project identity and checkpoint bytes must
match. [@dlcTraining302]

Set SKELLYCLICKER_TRAINING_PYTHON or edit Training Python to choose the isolated
runtime. Local environment discovery is a convenience, not an object restriction.

## Find and review new examples

Improve dataset / Find next examples scans the current recording's complete
synchronized videos with the selected checkpoint. It retains predictions and
compares them against available, gate-passing geometry projections. Initial API
defaults classify near misses above 0.03 projected-target diagonals, and major
failures at 0.5 diagonals or when fewer than half the reference points meet
confidence 0.2. These are heuristic proposal criteria, not label certification.
Temporal spacing defaults to 0.5 seconds per camera. Selection balances groups
and fills from the available group when the other is sparse. Previously reviewed
images, including removals, are not proposed again. The parent's validation tail
and guard are excluded from training additions.

Proposals remain separate from the dataset. Magenta marks show proposed geometry
labels; cyan crosses show predictions. Remove from batch edits this pending
review only. Add reviewed images generates labels for exactly the retained
camera-image identities. Existing labels and members remain; previous removals
are not silently restored. New bundles record their predecessors; historical
bundles are immutable. The review and completed analysis restore after reload.
Keep the chosen Starting model and click Start training for the expanded dataset.

Current scope is one ZED recording per project. Inference scans the full videos,
but automatic additions require an existing verified prepared pose. Missing or
rejected geometry is counted separately, never assumed correct. Merging different
prepared pose/calibration revisions is explicitly blocked. Automatic preparation
of uncovered proposal frames and multiple-recording aggregation remain unfinished.
A new analysis changes the displayed proposal, not historical artifacts or the
dataset. Cancelling analysis does not change training membership.

## Action prerequisites and project defaults

The training-set panel displays blockers outside the zoomable graph. Fresh
preparation remains a separate control; Open preparation controls leads there.
Use prepared frames restores a valid prepared range while retaining sampling
preferences. Preview is read-only and must succeed before Generate candidates is
enabled. Stale preview responses cannot enable generation for changed settings.
Server errors remain visible beside the actions.

The project manifest owns the selected STL revision and units. Browser-local
external draft paths cannot override that default. Creating a project copies the
chosen STL into recordings/<recording>/skellyclicker/inputs/targets/<object>/<revision>.
Its original source path is provenance only. New-project fields inherit available
recording, calibration and target values. Browsing alternate geometry makes a
temporary validated draft, not a replacement of existing target definitions.

## Log sessions

The backend LogHub identity establishes the viewer session. Closing the panel
retains and collects messages. Reload restores the bounded 10,000-record history
and deduplicates replay; a new backend lifetime starts a new viewer history.
Run logs on disk remain intact. Browser persistence failures are reported.


## Pose validation and checkpoint recommendations

New training snapshots freeze `pose-references.json` with the label-generating original-STL-to-camera transforms and source pose manifest hash. At each saved checkpoint the isolated DLC worker estimates a separate pose from predicted keypoints and the calibrated rectified camera using OpenCV RANSAC PnP and LM refinement [@opencvPoseValidation]. It never initializes the solver from the reference. Ordered authored points are in millimetres; reference translations are converted from metres once. This is single-camera evaluation for each image, not a joint stereo fit.

The dashboard adds mean position error (mm), mean orientation error (degrees of relative rotation), and pose failure rate (%). Position is measured at the original STL origin. Means include successful solves only; failure rate uses all validation images with an accepted, valid reference. Missing/rejected references are counted separately in each checkpoint's `pose-validation.json` and the recommendation reports reference coverage. These are agreements with the stereo/FoundationPose labels, not independent ground truth. Rotation compares the authored orientation directly; equivalent rotations of symmetric targets are not discounted.

Policy v1 uses confidence >= 0.2, at least six finite points, 200 RANSAC iterations, an 8-pixel inlier threshold, and at least six inliers covering half the usable points. Missing predictions, insufficient consensus, degenerate points, solver failure, nonfinite results and behind-camera estimates count as failures. A confidently wrong but geometrically consistent solve appears as a large position/orientation error, not necessarily a solver failure. Thresholds describe this evaluation policy, not a guarantee of acceptable tracking accuracy. Per-image reasons and estimated transforms are saved.

Recommendation v1 first minimizes pose failure rate. Among tied checkpoints it adds equally weighted ranks for mean position, orientation and keypoint errors; lower is better. Ties use keypoint error, then latest epoch. It compares only checkpoints with complete successful-pose metrics and matching reference counts within the selected run; exclusions and coverage are shown. When such comparison is unavailable, the explanation explicitly falls back to mean keypoint error (or latest checkpoint if no metrics). Historical runs are preserved and are not retroactively pose-evaluated. Training and validation loss computations are unchanged.

## Reviewing the next batch

The Generate training data workspace contains the pending batch, with an Add N images action above its comparison grid. Remove excludes a proposal from that batch. After publication, the batch collapses and displays a committed receipt with added count and before/after dataset counts. Go to Training changes views without starting a job. Inspect added batch reopens the historical comparison; its remove controls are absent because membership now belongs to the Training images catalog. Find next examples creates a new proposal batch with the selected starting model. Analysis details distinguish uncovered frames from reserved evaluation frames. Adding, failure and completion states stay visible above the grid.

Verification: worker pose tests run with the isolated DLC Python because OpenCV intentionally is not an application-backend dependency. Backend discovery skips these five tests; run `python -B backend/tests/test_pose_validation.py` using the configured training interpreter to execute them.

## Workspace cleanup (2026-11-06)
The shell uses public SDK WorkspaceTabs, WorkspaceToolbar, RunActivity and the existing Skull stylesheet. Viewer and Training share persistent next-run commands; the training controller and viewer stay mounted. The project/training-image sidebar is collapsible and retains its resizable layout. Configuration dialogs are portaled outside inactive panels. Checkpoint images live beside the training plots in a resizable two-column Training view. Old saved checkpoint-tab selections open Training.

Viewer Previous/Next training frame uses current persisted included camera-images, deduplicated by source frame and filtered for available playback indices. It pauses and awaits actual presented source identity. Ordinary play, pause, stepping and scrubbing remain separate. Empty selections and boundaries disable navigation; seeking and errors appear beside the controls. Dataset removal and Undo retain their original backend behavior.

Training exposes actual stages, elapsed time, epoch progress and snapshot receipt age. After 30 seconds without a received update, activity reports stale telemetry and stops pulsing; this is not a task-failure declaration. Reduced-motion preference disables the pulse. All recorded metric series remain available; next-run starting weights remain independent of displayed results. Accepted refinement batches offer Go to Training navigation; starting training remains a separate explicit action in Training.

Validation: SDK build and74 tests passed (one external playback-file test skipped); UI production build; training-navigation and training-workflow tests; isolated training-action-states and refinement-review fixtures; native-dataset-layout and native-workspace-cleanup checks. Native checks verified the61-image dataset was unchanged,4 saved plots and4 checkpoint images, ordinary playback and subset seeks, keyboard tabs, reload, graphs, logs, and constrained widths. No real training job was started for this UI validation. Native scripts require the running development app/CDP9224 and current prepared project; fixture scripts require frontend5176. Screenshot/report outputs belong in ignored .test-artifacts.


## Simple 2D recovery and configurable evaluation

New runs default to `pose_validation: false` and `checkpoint_metric: mean_px`. Evaluation settings are available above the results and in Configure training. Turning pose diagnostics off skips rigid pose estimation entirely; no pose metric or synthetic zero is emitted. The optional pose policy remains available explicitly. Recommendation can use mean pixel error or 95th-percentile pixel error; changing that control re-ranks the displayed run immediately and saves the choice for the next run. Historical charts are never rewritten. Legacy runs without a recorded policy retain their original policy when queried without an explicit override.

These controls do not change optimization. The official DLC head uses weighted heatmap MSE and location-refinement Huber losses; APP rigid pose diagnostics are separate from DLC's normal 2D location refinement. The `prepare` and `train` functions match pre-pose commit 7d6b43a. Parent initialization preserves learned model weights and resets the optimizer as before. There is no pose-driven early stopping. Configured maximum duration can stop a run before its epoch budget; the activity label now identifies that time-limit outcome, and saved checkpoints remain available.

Raw 2D error is Euclidean distance in native image pixels against frozen valid/in-bounds labels, with no prediction-confidence filter. Missing/nonfinite predictions are counted separately against the fixed labeled-point denominator. Finite-only mean and p95 curves remain available, but new 2D checkpoint ranking excludes incomplete prediction coverage. Historical checkpoints without coverage carry an explicit warning. Every evaluated image (all held-out images and the original fixed first training sample per camera) now retains raw predictions, confidence, labels, masks and errors in predictions.json; the checkpoint gallery links the selected epoch’s saved JSON. Raw invalid coordinates serialize as null, not zero. Evaluation emits an explicit progress stage.

Recovery evidence: fixed full-dataset inference on run4006e999 epochs1 and77 used identical52 training and8 validation images. Training mean pixel error2.17148→0.77782; validation4.88937→5.13969, with416/416 predicted validation points at both checkpoints. This demonstrates training-set fitting, not held-out improvement. An isolated one-epoch continuation with pose disabled completed, with validation5.17397px; disabling diagnostics alone is not an accuracy intervention. The user's project and saved run files were unchanged by these tests.


## Committed iteration receipts

Batch identity, creation time and source checkpoint distinguish saved proposals from new analysis. Find next examples replaces the displayed batch with the new run. Add publishes exactly the remaining reviewed camera images, preserves prior exclusions, and records immutable membership counts and added IDs. Repeating acceptance returns the existing job and receipt. A stale selection or label revision blocks publication; a failed project-pointer commit produces no success receipt. Current catalog and next-run input previews refresh from the returned selection revision, without requiring a WebSocket event. Existing frozen training inputs remain unchanged. Historical receipts are reconstructed only when their immutable selection lineage is available.

Regression evidence: backend receipt tests cover duplicate acceptance, failed publication, stale proposals, retained exclusions and the next immutable training snapshot. The refinement UI fixture covers removing one proposal, adding the exact remainder, receipt restoration after reload, navigation without starting training, and a new batch replacing accepted history.


## Checkpoint image browser
Training keeps curves on the left and saved checkpoint samples on the right. The epoch slider indexes actual saved prediction epochs (including sparse save intervals), not fabricated intermediate images. Follow latest tracks newly saved epochs; manual browsing stays on the chosen epoch and never changes the next run’s starting checkpoint. A completed 100-epoch run with save_every=1 exposes100 saved epochs.

Image size, target crop/full frame, annotations, raw-on-hover and the SDK full-resolution image dialog are available in the gallery. The API renders frozen source images with saved prediction coordinates and frozen labels; it does not rerun inference or modify historical outputs. Crop bounds use the reference points consistently across epochs and annotation modes. The four fixed training/validation camera samples are shown, rather than implying that every training image was evaluated. Missing data and unavailable saved predictions are reported explicitly.


## Add images after a training round

The outlined **Add training images** action stays above the Training results.
It opens review with the displayed run's recommended checkpoint (including its
hash and ranking explanation), independently of an older Starting model choice.
The default target is 100 additional camera images. **Analyze recording and
recommend images** launches inference; opening the dialog launches nothing.

Analysis balances near misses and major failures, then favors source viewpoint
bins underrepresented in the existing dataset before breaking ties by error.
It scans the one synchronized recording supported by this adapter. Current
members, explicit human removals, and validation/guard frames are not proposed.
Images omitted by a recorded Best-N ranking remain candidates. Verified source
poses are required; the target count is a maximum, not a guarantee.

Review magenta reference labels against cyan predictions. **Add N images**
preserves existing members and commits only the kept additions. The receipt
reports the actual before/added/after counts. **Go to Training** selects the
recommended model for continuation; starting training remains a separate action.
Training loss is unchanged. Older run datasets and checkpoints remain immutable.

The acquisition metric is raw 2D disagreement with prepared STL projections.
Shared multiview reconstruction/reprojection error and Viewer playback of the
saved full-recording predictions are not yet connected to this workflow.
