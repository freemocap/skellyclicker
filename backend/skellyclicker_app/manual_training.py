"""Train the existing DLC worker from clicked camera frames in an opened recording."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from .gpu_runtime import run_external

import cv2
from freemocap_sdk.storage import atomic_json, file_digest
from .manual_recording import LabelDocument, labeling_bundle
from freemocap.core.playback.media_selection import PlaybackVideoSource, video_source_folder


def train_round(recording, output, python, training_frames, validation_frames, epochs, parent=None):
    output.mkdir(parents=True, exist_ok=False)
    freeze_clicks(recording, output, training_frames, validation_frames, epochs, parent)
    worker = Path(__file__).parent/"workers/train_dlc.py"
    for mode in ("prepare","train"):
        run_external([python,str(worker),mode,str(output)])


def freeze_clicks(recording, output, training_frames, validation_frames, epochs, parent=None, *, save_every=1, doc=None, check_cancelled=lambda: None):
    if not training_frames or not validation_frames or training_frames & validation_frames:
        raise ValueError("Choose disjoint, nonempty training and validation moments")
    if doc is None:
        doc = LabelDocument.model_validate_json((recording/"skellyclicker/manual-labels.json").read_bytes())
    if doc.recording_id != recording.name:
        raise ValueError("Labels belong to a different recording")
    bundle = labeling_bundle(recording.name, str(recording.parent))
    source = PlaybackVideoSource.SYNCHRONIZED
    folder = video_source_folder(recording=recording, source=source)
    wanted = training_frames | validation_frames
    grouped = defaultdict(dict)
    for obs in doc.observations:
        if obs.origin == "click" and obs.source_frame in wanted:
            grouped[obs.camera_id, obs.source_frame][obs.point] = [obs.x_px, obs.y_px]
    dataset = output/"dataset"
    dataset.mkdir()
    rows, files = [], {}
    clocks = {item.video_filename:item.timeline.frame_numbers for item in bundle.media if item.video_source == source}
    for camera_index, view in enumerate(bundle.videos.sources[source].videos):
        capture = cv2.VideoCapture(str(folder/view.filename))
        try:
            frame_indices = {frame:i for i,frame in enumerate(clocks[view.filename])}
            for source_frame in sorted(wanted):
                check_cancelled()
                observations = grouped.get((view.video_id,source_frame))
                if not observations:
                    continue
                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_indices[source_frame])
                ok,image = capture.read()
                if not ok:
                    raise ValueError(f"Could not decode {view.filename} at {source_frame}")
                name = f"frame-{source_frame:08d}-view-{camera_index}.png"
                path = dataset/name
                if not cv2.imwrite(str(path),image):
                    raise OSError(f"Could not save {path}")
                files[name] = {"sha256":file_digest(path)}
                rows.append({"path":name,"image_id":path.stem,"source_frame":source_frame,"camera_id":view.video_id,
                             "width":image.shape[1],"height":image.shape[0],
                             "xy":[observations.get(point,[None,None]) for point in doc.tracked_point_names],
                             "valid":[point in observations for point in doc.tracked_point_names],
                             "split":"training" if source_frame in training_frames else "validation"})
        finally:
            capture.release()
    if {row["source_frame"] for row in rows} != wanted:
        raise ValueError("Requested moments must contain independent clicks on a source camera")
    manifest = dataset/"manifest.json"
    atomic_json(manifest,{"keypoint_names":doc.tracked_point_names,"files":files,"label_origin":"click"})
    request = {"dataset":str(dataset),"dataset_sha256":file_digest(manifest),"images":rows,
               "epochs":epochs,"save_every":min(save_every, epochs),"batch_size":1,"seed":42}
    if parent:
        request.update(initial_checkpoint=str(parent),initial_checkpoint_sha256=file_digest(parent))
    atomic_json(output/"worker-request.json",request)
    return request


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--training-python",required=True,type=Path)
    parser.add_argument("--train",nargs="+",type=int,required=True)
    parser.add_argument("--validate",nargs="+",type=int,required=True)
    parser.add_argument("--epochs",type=int,default=10)
    parser.add_argument("--parent-checkpoint",type=Path)
    args = parser.parse_args()
    if args.epochs < 1:
        parser.error("epochs must be positive")
    train_round(args.recording.resolve(),args.output.resolve(),args.training_python.resolve(),
                set(args.train),set(args.validate),args.epochs,args.parent_checkpoint)
