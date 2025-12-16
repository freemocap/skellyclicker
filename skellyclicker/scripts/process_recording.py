import shutil
from pathlib import Path

from skellyclicker.core.deeplabcut_handler.deeplabcut_handler import DeeplabcutHandler

import matplotlib as plt
import logging

from skellyclicker.scripts.flip_video import flip_eye1_video, flip_eye0_video


plt.set_loglevel('WARNING')
logging.getLogger('PIL').setLevel(logging.WARNING)

def copy_files(files: list[Path], destination: Path):
    if len(files) == 0:
        raise ValueError(f"attemped to copy files to {str(destination)} but no files provided")
    print(f"Copying files {[file.name for file in files]} to {str(destination)}")
    for file_path in files:
        shutil.copy2(src = file_path, dst=destination)

def process_recording(video_folder: Path, deeplabcut_folder: Path | str, output_folder: Path | None = None, suffix: str = ""):
    if output_folder is None:
        output_folder = video_folder.parent
    deeplabcut_folder = Path(deeplabcut_folder)
    dlc_output_folder = output_folder / "dlc_output"
    annotated_videos_folder = output_folder / "annotated_videos" / f"annotated_videos_{deeplabcut_folder.stem}{suffix}"
    dlc_output_folder.mkdir(exist_ok=True, parents=True)
    annotated_videos_folder.mkdir(exist_ok=True, parents=True)
    analyze_videos_output = dlc_output_folder / f"{deeplabcut_folder.stem}{suffix}"
    deeplabcut_config = deeplabcut_folder / "config.yaml"
    handler = DeeplabcutHandler.load_deeplabcut_project(project_config_path=str(deeplabcut_config))
    video_paths = [str(path) for path in video_folder.glob("*.mp4")]
    print(f"VIDEO PATHS in {video_folder}: \n{video_paths}")
    handler.analyze_videos(video_paths=video_paths, output_folder=analyze_videos_output, annotate_videos=True)

    annotated_video_paths = list(analyze_videos_output.glob("*.mp4"))
    copy_files(files = annotated_video_paths, destination=annotated_videos_folder)

def run_all_models(recording_path: Path, include_eye: bool, flip_eye_0: bool = False, flip_eye_1: bool = False):
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
        process_recording(video_folder=eye_video_path, deeplabcut_folder=best_eye_model_folder, output_folder=eye_data_path)
        if flip_eye_0:
            flip_eye0_video(eye_data_folder=eye_data_path)  # use this for october recordings
        if flip_eye_1:
            flip_eye1_video(eye_data_folder=eye_data_path)  # use this for july recordings
        if flip_eye_0 or flip_eye_1:
            print("standard eye video processed, processing flipped eye videos")
            flipped_eye_videos_path = eye_video_path / "flipped_eye_videos"
            process_recording(video_folder=flipped_eye_videos_path, deeplabcut_folder=best_eye_model_folder, output_folder=eye_data_path, suffix="_flipped")
        print("eye videos processed")
    else:
        best_mocap_model_folder = "/home/scholl-lab/deeplabcut_data/head_body_noeyecam_v0"
    print("Processing mocap videos...")
    process_recording(video_folder=mocap_video_path, deeplabcut_folder=best_mocap_model_folder)
    print("mocap videos processed")
    print("Processing mocap videos with toy model...")
    process_recording(video_folder=mocap_video_path, deeplabcut_folder=best_toy_model_folder)
    print("toy model processed")

if __name__=="__main__":
    # set this as needed to flip eye videos correctly
    flip_eye_0 = True  # set True for October Videos
    flip_eye_1 = False  # Set True for July Videos

    # use /full_recording or /clips/{clip_name}
    recording_path = Path("/home/scholl-lab/ferret_recordings/session_2025-10-12_ferret_402_E03/full_recording")
    include_eye = True

    run_all_models(recording_path, include_eye, flip_eye_0=flip_eye_0, flip_eye_1=flip_eye_1)

    # recording_path = Path("/home/scholl-lab/ferret_recordings/session_2025-10-12_ferret_402_E03/full_recording")

    # run_all_models(recording_path, include_eye, flip_eye_0=flip_eye_0, flip_eye_1=flip_eye_1)

    # recording_path = Path("/home/scholl-lab/ferret_recordings/session_2025-07-07_ferret_753_EyeCameras_P39_E11/full_recording")

    # run_all_models(recording_path, include_eye, flip_eye_0=flip_eye_0, flip_eye_1=flip_eye_1)
