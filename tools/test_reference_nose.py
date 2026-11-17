"""Compare two manually trained nose checkpoints with a numerical FreeMoCap test_data run.

Run with backend Python: test_reference_nose.py PREPARED_RECORDING ROUND1 ROUND2 --training-python PATH.
The DLC interpreter runs only inference. Reference coordinates are first read during scoring.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np


def predict(recording, run):
    from deeplabcut.pose_estimation_pytorch.apis.utils import get_pose_inference_runner
    config = json.loads((run/"prepared.json").read_bytes())
    trained = json.loads((run/"trained.json").read_bytes())
    model = get_pose_inference_runner(model_config=Path(config["pose"]), snapshot_path=run/trained["checkpoint"],
                                      batch_size=1, device="cuda:0", max_individuals=1)
    predictions = {}
    for path in sorted((recording/"synchronized_videos").glob("*.mp4")):
        frames = []
        cap = cv2.VideoCapture(str(path))
        try:
            while True:
                ok, image = cap.read()
                if not ok:
                    break
                result = model.inference([cv2.cvtColor(image,cv2.COLOR_BGR2RGB)])[0]["bodyparts"][0]
                if len(result) != 1:
                    raise ValueError("Expected a single nose keypoint")
                frames.append(result[0][:2])
        finally:
            cap.release()
        predictions[path.name] = np.array(frames)
    np.savez(run/"reference-nose-predictions.npz", **predictions)


def score(recording, run, excluded):
    import pyarrow.parquet as pq
    from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
    from freemocap.core.reconstruction.coordinate_conventions import CALIBRATION_TO_RECONSTRUCTION
    from freemocap.core.tasks.triangulation.helpers.triangulate_simple import triangulate_simple_batch
    from freemocap.tools.datasets.catalog import TEST_DATA
    from skellyclicker_app.manual_recording import labeling_bundle
    expected = TEST_DATA.expected_frame_count
    parquet = recording/f"{recording.name}_data.parquet"
    columns = ["frame_number","reference_frame","component","value","channel","source","units"]
    truth = pq.read_table(parquet,columns=columns,filters=[("name","in",["body.nose","nose"]),
                        ("channel","in",["OVERLAY_2D","RAW_KEYPOINTS_3D"])]).to_pylist()
    values = {}
    for row in truth:
        key = (row["channel"],row["reference_frame"],row["component"],row["frame_number"])
        if key in values:
            raise ValueError(f"Ambiguous reference observation {key}")
        values[key] = row["value"]
    keep = [f for f in range(expected) if f not in excluded]
    def track(channel,space,axes):
        return np.array([[values.get((channel,space,a,f),np.nan) for a in axes] for f in keep],dtype=float)
    bundle = labeling_bundle(recording.name,str(recording.parent))
    metadata = json.loads(pq.read_schema(parquet).metadata[b"freemocap.recording"])
    run_meta = metadata["runs"][str(metadata["selected_run_id"])]
    geometry, = run_meta["camera_geometry"].values()
    cameras = {cam.id:cam for cam in map(CameraModel.model_validate,geometry)}
    normalized, extrinsics, pixel_errors = [], [], []
    with np.load(run/"reference-nose-predictions.npz") as predictions:
        for view in bundle.videos.sources["synchronized"].videos:
            cam = cameras[view.video_id]
            xy = predictions[view.filename]
            if xy.shape != (expected,2):
                raise ValueError(f"Unexpected prediction shape for {view.filename}: {xy.shape}")
            xy = xy[keep].astype(float)
            baseline = track("OVERLAY_2D",f"camera:{view.filename}:image","xy")
            pixel_errors.extend(np.linalg.norm(xy-baseline,axis=1))
            normalized.append(cv2.undistortPoints(xy[:,None],cam.intrinsics.to_camera_matrix(),
                                                   cam.intrinsics.to_dist_coeffs()).reshape(-1,2))
            extrinsics.append(np.column_stack([cam.extrinsics.rotation_matrix,cam.extrinsics.translation]))
    xy = np.stack(normalized,axis=1)
    finite = np.isfinite(xy).all(axis=(1,2))
    xyz = np.full((len(keep),3),np.nan)
    if finite.any():
        xyz[finite] = triangulate_simple_batch(points_batch=xy[finite],extrinsics_mats=np.array(extrinsics)) @ CALIBRATION_TO_RECONSTRUCTION.matrix.T
    baseline = track("RAW_KEYPOINTS_3D","calibrated_world","xyz")
    def metrics(errors):
        errors = np.array(errors)
        valid = errors[np.isfinite(errors)]
        if not len(valid):
            raise ValueError("No comparable nose observations on the holdout")
        return dict(compared=len(valid),expected=len(errors),mean=float(valid.mean()),median=float(np.median(valid)),
                    p95=float(np.percentile(valid,95)))
    return {"excluded_training_frames":sorted(excluded),"holdout_frames":len(keep),
            "error_px":metrics(pixel_errors),"error_mm":metrics(np.linalg.norm(xyz-baseline,axis=1))}


if __name__ == "__main__":
    if len(sys.argv)==4 and sys.argv[1]=="--predict":
        predict(Path(sys.argv[2]),Path(sys.argv[3]))
    else:
        parser=argparse.ArgumentParser(description=__doc__)
        parser.add_argument("recording",type=Path)
        parser.add_argument("rounds",type=Path,nargs="+")
        parser.add_argument("--training-python",type=Path,required=True)
        args=parser.parse_args()
        excluded=set()
        for run in args.rounds:
            request=json.loads((run/"worker-request.json").read_bytes())
            manifest=json.loads((Path(request["dataset"])/"manifest.json").read_bytes())
            if manifest["keypoint_names"] != ["nose"]:
                raise ValueError("Expected a nose-only model")
            excluded.update(row["source_frame"] for row in request["images"] if row["split"]=="training")
        for run in args.rounds:
            subprocess.run([args.training_python,__file__,"--predict",args.recording,run],check=True)
            summary=score(args.recording,run,excluded)
            (run/"reference-nose-errors.json").write_text(json.dumps(summary,indent=2))
            print(run,summary,flush=True)
