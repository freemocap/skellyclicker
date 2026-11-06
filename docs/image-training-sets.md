# Creating image training sets

Open **Create image training set**, leave **Entire recording (every frame)** selected, and click **Generate all images**.

The default starts at source frame zero, includes every source frame and both camera images, applies no fit filter, and imposes no image-count cap. Existing matching preparation can be reused; incomplete coverage triggers full-recording preparation. The action then validates the prepared inputs and generates labels automatically. There is no separate preview gate to click through.

The command area reports the frame/image count when known. Running preparation shows its stage and completed frames; labeling shows the active operation. Cancel stops the active backend job. Closing the dialog keeps the controller mounted; reopening or reloading recovers the recorded job. **Open generated images** refreshes the project, selects Viewer, and expands the image catalog. Training remains a separate action.

**Custom range / sampling** exposes the first source frame, number of frames, and sampling interval. These are explicit overrides. Opening the workflow defaults to the entire recording rather than restoring an old sampled range.

## Preserving existing work

Full preparation processes the requested recording. Before activation, the expanded reference bundle retains complete reference rows and per-frame artifacts for all moments represented in the existing label set, including excluded camera images. Its provenance records the old pose/label manifests and retained source frames. Other frames use the new preparation run.

The application stages immutable revisions of the existing labels and selection against that expanded reference bundle, preserving their data and membership. It builds the corresponding playback without activating it. The project switches its preparation, labels, selection and playback pointers together only after these operations succeed and the project still matches the captured baseline. Cancellation or failure before activation leaves the previous project usable. Previous bundles remain immutable.

Label generation then uses the normal matching-pose-manifest merge contract: existing label rows and exclusions survive; newly generated image identities use the existing proposed-inclusion behavior. Training-reference pose identity checks remain enforced. This operation does not relabel existing reviewed images against newly fitted poses.

## Validation

Backend: `test_preparation.py`, `test_labels.py`, and `test_playback_adapter.py` cover unrestricted/full-recording requests, immutable staging, activation failure, retained reference rows, existing labels and exclusions.

Frontend: `training-workflow.test.mjs` verifies whole-recording defaults and explicit sampling. `image-generation.mjs` runs an isolated browser fixture through preparation, validation, labeling, progress, close/reopen, reload recovery, cancellation, errors and result opening. It requires the development frontend on port 5176 and writes screenshots to ignored `.test-artifacts/`; it does not process the user's recording.
