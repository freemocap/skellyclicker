# Qualify a SkellyClicker desktop installer

Use Windows x64, Apple Silicon macOS, and Ubuntu x64 clean test installations. Run the GPU portion on Windows and Ubuntu with supported NVIDIA hardware. Keep one evidence record per installer and machine. Record the candidate commit, CI run, installer name and SHA-256, OS version and architecture, GPU and driver (when applicable), install method, and any setup performed. Use the downloaded release candidate throughout. Launch it through its installed desktop entry.

The CI smoke job uses a fresh runner per OS. It installs the NSIS package, copies the app from its DMG, or installs the DEB with its runtime dependencies. It starts the installed backend directly, checks the SDK readiness event, verifies the SkellyClicker HTTP status, requests shutdown and checks that the server releases its port. It also runs the packaged Node, encodes two H.264 frames with the packaged FFmpeg, and reads them with the packaged FFprobe. The job logs the tested installer digest. The desktop and GPU checks below still require the reference input.

## Reference input

Use the Benchy SVO, camera calibration, authored STL and keypoint definition that produced the prepared `benchy-sfn26` project described in [PLAYBACK.md](../PLAYBACK.md). Obtain their digests and the chosen source frame range once from the same reference copy and use those values on every machine. Record the prepared project UUID and pose-manifest hash. The reference data is external to this repository. A generated placeholder SVO cannot qualify ZED replay.

Give each tester a disposable, writable copy of the prepared project, with linked source files available at the paths expected by its recording descriptor. Confirm all three machines opened the same immutable source identities. For a fresh GPU job, create a **new** disposable project from the original inputs to avoid reusing previous preparations and checkpoints. Pick a bounded frame range containing fitted Benchy poses and enough distinct training and validation moments for one epoch. Use the same range on both GPU machines.

## Installed desktop

1. Install through the normal OS installer. Launch from the Start menu, Applications, or the Ubuntu applications launcher. Record evidence of the running application and backend paths. Open the prepared project using the app's project picker.
2. In Viewer, show both synchronized cameras. Play, pause, seek to the first, middle and last frame, and play again. Verify the two decoded views show the same source moment and advance together. Record the displayed frame numbers, a short screen recording of playback, and both paused views. Check the raw media and pose overlays actually render.
3. Test the requested annotation round trip when the candidate supplies the point editor. Record camera, source frame, keypoint name, previous value, and a distinct valid image-space coordinate. Make the edit in the installed window, save, quit the entire app, relaunch and reopen the project. Verify the same keypoint, frame and camera have the saved value and the opposite camera keeps its original value. Attach the persisted record and before/after screenshots. Mark this check blocked when the editor is unavailable.
4. The existing per-image review control can be exercised independently. In a disposable project with generated labels, find an included stereo pair. Pause and use **Remove from training set** on one camera. Record the source frame, camera, removed image ID, opposite camera image ID, and the new project `active_review` revision. Quit and reopen. Confirm the catalog excludes exactly the chosen image, retains its mate, and still points to that review revision. The review manifest and `selection.parquet` identify the saved membership. Report this observation separately from point editing.

## Installed GPU workflow

1. Record device and driver from `nvidia-smi`. Follow the candidate's published runtime setup instructions. Launch the installed app normally and record the runtime checks and versions it reports.
2. Create the fresh project, select the reference inputs and prepare the chosen source range. Verify the app reports completion, renders both cameras and fitted poses, and shows at least one accepted fit. Record the run ID, source range and acceptance count. Save the new preparation's `manifest.json`, `summary.json`, and `provenance.json` from this run.
3. Generate training labels from this preparation. Include enough eligible camera images to get nonempty training and held-out validation splits in the training preview. Record the split counts. Select a fresh model and set **epochs** and **save every** to 1, with enough time for one epoch. Run training, wait for completion, and open the saved epoch in **Checkpoint images**. Record the run ID, checkpoint digest, and validation predictions from this epoch. The worker runs checkpoint inference during evaluation. Save the app log and prediction output.
4. Audit the emitted files using the command below. It can run separately on a QA machine with Python 3.11+ and a copy of the installer and project tree. For the prepared-project desktop check, omit `--training-run`. Keep its JSON output with the observed desktop behavior. A successful artifact check by itself does not exercise an installed process or its webview.

```text
python tools/verify_installed_outputs.py --installer <downloaded-package> --project <project-manifest.json> --source-sha256 <pinned-svo-digest> --start <first-source-frame> --count <frame-count> --training-run <project/recordings/.../skellyclicker/training-runs/run-id>
```

The verifier checks media content hashes, synchronized frame numbers and times, preparation identity, and the expected frame range. For GPU runs it also checks the frozen dataset against the preparation, the trained checkpoint digest against the inference record, and finite predictions for held-out labeled points. Record failed checks, missing credentials, missing inputs and unavailable hardware explicitly alongside the last successful step.
