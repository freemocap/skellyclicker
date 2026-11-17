"""Audit outputs from the installed-app procedure in docs/installer-qualification.md."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def member(root, name):
    path = (root / name).resolve()
    require(path.is_relative_to(root) and path != root, f"Path outside artifact root: {name}")
    return path


def verify_playback(root, project, start, count, source_sha):
    playback = member(root, project["playback_result"])
    prepared = member(root, project["sample_result"])
    pose_sha = digest(prepared / "manifest.json")
    authority = read(prepared / "manifest.json")
    require(authority["descriptor"]["source_sha256"] == source_sha, "Different SVO input")
    provenance = read(playback / "provenance.json")
    require(provenance["source_manifest_sha256"] == pose_sha, "Playback refers to another preparation")
    summary = read(prepared / "summary.json")
    require(digest(prepared / "summary.json") == authority["files"]["summary.json"]["sha256"],
            "Preparation summary changed")
    frames = [row["source_frame"] for row in summary["frames"]]
    require(frames == list(range(start, start + count)), "Unexpected prepared frame range")
    timestamps = [int(row["timestamp_ns"]) for row in summary["frames"]]
    require(all(a < b for a, b in zip(timestamps, timestamps[1:])), "Source timestamps out of order")
    require(timestamps == list(map(int, provenance["source_timestamps_ns"])), "Source clock mismatch")
    manifest = read(playback / "playback.json")
    run = next(item for item in manifest["runs"] if item["run_id"] == manifest["selected_run_id"])
    locations = read(playback / "media.json")
    hashes = read(playback / "media_hashes.json")
    cameras = set()
    for media in run["media"]:
        if media["video_source"] != "synchronized":
            continue
        timeline = media["timeline"]
        require(timeline["frame_numbers"] == frames, "Camera frame identities differ")
        seconds = [(stamp - timestamps[0]) / 1e9 for stamp in timestamps]
        require(len(timeline["timestamps_s"]) == count and
                all(math.isclose(a, b, abs_tol=1e-8) for a, b in zip(timeline["timestamps_s"], seconds)),
                "Camera timestamps differ")
        name = media["video_filename"]
        path = member(root, locations[name])
        require(path.stat().st_size > 0 and digest(path) == hashes[name]["sha256"],
                f"Missing or changed video: {name}")
        cameras.add(timeline["source"])
    require(cameras == {"left", "right"}, "Missing stereo camera")
    return {"playback_revision": manifest["revision"], "pose_manifest_sha256": pose_sha,
            "first_source_frame": start, "frame_count": count,
            "accepted_frames": sum(row["accepted"] is True for row in summary["frames"])}


def verify_training(root, project, run, source_sha, playback):
    run = run.resolve()
    require(run.is_relative_to(root) and run.parent.name == "training-runs",
            "Select a training run inside this disposable project")
    result = read(run / "result.json")
    require(result["run_id"] == run.name, "Unexpected training run")
    dataset = member(root, result["dataset"]["path"])
    dataset_sha = digest(dataset / "manifest.json")
    trained = result["trained"]
    require(dataset_sha == result["dataset"]["manifest_sha256"] == trained["dataset_sha256"],
            "Frozen training dataset differs")
    dataset_info = read(dataset / "manifest.json")
    require(dataset_info["project_uuid"] == project["uuid"] and dataset_info["source_sha256"] == source_sha,
            "Training used another project or recording")
    references = read(dataset / "pose-references.json")
    require(references["pose_manifest_sha256"] == playback["pose_manifest_sha256"],
            "Training used another pose preparation")
    require(playback["accepted_frames"] > 0, "No pose passed the preparation gates")
    epoch = trained["epochs"]
    require(type(epoch) is int and epoch >= 1, "No trained epoch")
    checkpoint = member(run, trained["checkpoint"])
    require(checkpoint.stat().st_size > 0, "Empty checkpoint")
    checkpoint_sha = digest(checkpoint)
    predictions = read(run / "previews" / f"epoch-{epoch:06d}" / "predictions.json")
    require(checkpoint_sha == trained["checkpoint_sha256"] == predictions["checkpoint_sha256"]
            and predictions["epoch"] == epoch, "Inference checkpoint differs from trained checkpoint")
    points = 0
    for row in predictions["images"]:
        if row["split"] != "validation":
            continue
        for labeled, truth, predicted in zip(row["labeled"], row["truth_xy"], row["keypoints"], strict=True):
            if labeled and all(value is not None for value in truth):
                require(len(predicted) == 3 and all(v is not None and math.isfinite(v) for v in predicted),
                        f"Missing or nonfinite prediction on {row['image_id']}")
                points += 1
    require(points > 0 and points == predictions["coverage"]["expected_points"],
            "No verified held-out prediction coverage")
    return {"run_id": run.name, "epoch": epoch, "dataset_sha256": dataset_sha,
            "checkpoint_sha256": checkpoint_sha, "finite_validation_predictions": points}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True, help="Project manifest from qualification run")
    parser.add_argument("--source-sha256", required=True, help="Pinned digest of the reference SVO")
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--training-run", type=Path, help="Additionally check this run's GPU workflow outputs")
    args = parser.parse_args()
    require(args.start >= 0 and args.count >= 2, "Supply a positive multi-frame reference range")
    project = read(args.project)
    root = args.project.resolve().parent
    playback = verify_playback(root, project, args.start, args.count, args.source_sha256)
    report = {"installer_sha256": digest(args.installer), "source_sha256": args.source_sha256,
              "project_uuid": project["uuid"], "playback_artifacts": playback}
    if args.training_run:
        report["training_artifacts"] = verify_training(root, project, args.training_run,
                                                       args.source_sha256, playback)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, TypeError, ValueError, StopIteration) as error:
        sys.exit(f"Output verification failed: {error}")
