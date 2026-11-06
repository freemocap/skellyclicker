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

The pending batch has an Add reviewed images action above its scrollable comparison grid. Remove excludes a proposal from that batch. After publication, the batch collapses and the header says Images added, with Train next round beside it. Inspect added batch reopens the historical comparison; its remove controls are absent because membership now belongs to the Training images catalog. Find next examples creates a new proposal batch with the selected starting model. Analysis details distinguish uncovered frames from reserved evaluation frames. Adding, failure and completion states stay visible above the grid.

Verification: worker pose tests run with the isolated DLC Python because OpenCV intentionally is not an application-backend dependency. Backend discovery skips these five tests; run `python -B backend/tests/test_pose_validation.py` using the configured training interpreter to execute them.
