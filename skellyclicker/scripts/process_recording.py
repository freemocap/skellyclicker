import sys
from pathlib import Path

import matplotlib as plt
import logging

from skellyclicker.scripts.process_folder import process_folder


plt.set_loglevel('WARNING')
logging.getLogger('PIL').setLevel(logging.WARNING)

def run_all_models(recording_path: Path, include_eye: bool, include_body: bool = True, include_toy: bool = True):
    mocap_video_path = recording_path / "mocap_data" / "synchronized_corrected_videos"
    if not mocap_video_path.exists():
        mocap_video_path = recording_path / "mocap_data" / "synchronized_videos"
    best_toy_model_folder = "/home/scholl-lab/deeplabcut_data/toy_model_v2"
    if include_eye:
        eye_data_path = recording_path / "eye_data" 
        eye_video_path = eye_data_path / "eye_videos"

        best_eye_model_folder = "/home/scholl-lab/deeplabcut_data/eye_model_v3"
        best_mocap_model_folder = "/home/scholl-lab/deeplabcut_data/head_body_eyecam_retrain_test_v2"

        print("Processing eye videos...")
        process_folder(video_folder=eye_video_path, deeplabcut_folder=best_eye_model_folder, output_folder=eye_data_path)
        print("eye videos processed")
    else:
        best_mocap_model_folder = "/home/scholl-lab/deeplabcut_data/head_body_noeyecam_v0"
    if include_body:
        print("Processing mocap videos...")
        process_folder(video_folder=mocap_video_path, deeplabcut_folder=best_mocap_model_folder)
        print("mocap videos processed") 
    if include_toy:
        print("Processing mocap videos with toy model...")
        process_folder(video_folder=mocap_video_path, deeplabcut_folder=best_toy_model_folder)
        print("toy model processed")

if __name__=="__main__":
    # use /full_recording or /clips/{clip_name}
    recording_path = Path("/home/scholl-lab/ferret_recordings/session_2025-07-09_ferret_753_EyeCameras_P41_E13/full_recording")
    include_eye = True
    include_body = True
    include_toy = True

    if len(sys.argv) >= 2:
        recording_folder = Path(sys.argv[1])
        include_eye = True
        include_body = True
        include_toy = True
    else:
        recording_folder = recording_path
        print(f"Using default directory: {recording_folder}")

    if not recording_folder.exists():
        print(f"Error: Directory does not exist: {recording_folder}")
        print("\nUsage: python process_recording.py [recording_folder] {--skip-eye | -e} {--skip-body | -b} {--skip-toy | -t}")
        sys.exit(1)

    flags = [a for a in sys.argv[1:] if a.startswith("-")]

    # Process boolean flags
    for flag in flags:
        if flag in ("--skip-eye", "-e"):
            include_eye = False
        elif flag in ("--skip-body", "-b"):
            include_body = False
        elif flag in ("--skip-toy", "-t"):
            include_toy = False
        else:
            print(f"Warning: unknown flag {flag}")

    run_all_models(recording_folder, include_eye, include_body, include_toy)
