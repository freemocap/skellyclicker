# Training dashboard

The Viewer remains mounted when switching to Training dashboard. The SDK owns
pipeline configuration, full retained WebSocket snapshots, scalar plots and
sample preview rendering. SkellyClicker owns the dataset split and DLC adapter.

Include is review and approval. Automatic initial inclusion is a proposal;
Include/Exclude establishes the selection and Start training freezes it without
a second gate. The frozen snapshot retains all included images, exact int64
source timestamps, stereo moment identity, ordered labels, calibration and STL.
Labels retain pose_projection origin independently of human approval.

Validation is the final configured fraction of selected moments. A timestamp
based guard interval separates it from training; both cameras remain together.
Guard images remain in the snapshot but do not enter optimization or evaluation.
The small initial fixture verifies plumbing, not generalization quality.

The first adapter is DeepLabCut 3.0.2 / ResNet-50 using an isolated interpreter.
It uses official dataset creation, verifies saved split filenames, registers a
BaseLogger for epoch losses, and uses bounded official train API calls with official
checkpoint continuation. No training loop is patched. At each configured save
interval it reloads the actual checkpoint for fixed sample previews and native
pixel errors on the frozen validation set. This adds explicit evaluation time
between training segments. [@dlcTraining302]

Run data lives under the SDK recording extension's training-runs/<run-id>.
Raw JSONL events are durable; the SDK retains a bounded display history. PNG
previews and checkpoint identity are tied to actual epochs, not current UI time.
Cancellation writes STOP; the adapter checks it at epoch logger and inference
boundaries. After 15 seconds the app terminates only its owned worker. Completed
checkpoints remain; an interrupted partial epoch is not claimed as saved.

Set SKELLYCLICKER_TRAINING_PYTHON or edit Training Python to select the environment.
The existing local environment is discovered as an initial convenience, not an
object restriction. No old object-specific checkpoint is loaded by default.

Choose Configure training, review the included images and configured epoch/time limits,
then choose Start training to submit the actual run. View progress is available
only while running; it does not create a second run.
