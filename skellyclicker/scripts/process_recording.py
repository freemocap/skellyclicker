import shutil
from pathlib import Path

from skellyclicker.core.deeplabcut_handler.deeplabcut_handler import DeeplabcutHandler

import matplotlib as plt
import logging
plt.set_loglevel('WARNING')
logging.getLogger('PIL').setLevel(logging.WARNING)

def copy_files(files: list[Path], destination: Path):
    if len(files) == 0:
        raise ValueError(f"attemped to copy files to {str(destination)} but no files provided")
    print(f"Copying files {[file.name for file in files]} to {str(destination)}")
    for file_path in files:
        shutil.copy2(src = file_path, dst=destination)

def process_recording(video_folder: Path, deeplabcut_folder: Path | str):
    deeplabcut_folder = Path(deeplabcut_folder)
    dlc_output_folder = video_folder.parent / "dlc_output"
    annotated_videos_folder = video_folder.parent / "annotated_videos" / f"annotated_videos_{deeplabcut_folder.stem}"
    dlc_output_folder.mkdir(exist_ok=True)
    annotated_videos_folder.mkdir(exist_ok=True, parents=True)
    analyze_videos_output = dlc_output_folder / deeplabcut_folder.stem
    deeplabcut_config = deeplabcut_folder / "config.yaml"
    handler = DeeplabcutHandler.load_deeplabcut_project(project_config_path=str(deeplabcut_config))
    video_paths = [str(path) for path in video_folder.glob("*.mp4")]
    print(f"VIDEO PATHS: {video_paths}")
    handler.analyze_videos(video_paths=video_paths, output_folder=analyze_videos_output, annotate_videos=True)

    annotated_video_paths = list(analyze_videos_output.glob("*.mp4"))
    copy_files(files = annotated_video_paths, destination=annotated_videos_folder)

if __name__=="__main__":
    # use /full_recording or /clips/{clip_name}
    recording_path = Path("/home/scholl-lab/ferret_recordings/session_2025-07-11_ferret_757_EyeCamera_P43_E15__1/clips/0m_37s-1m_37s")
    include_eye = True

    mocap_video_path = recording_path / "mocap_data" / "synchronized_corrected_videos"
    if not mocap_video_path.exists():
        mocap_video_path = recording_path / "mocap_data" / "synchronized_videos"
    best_toy_model_folder = "/home/scholl-lab/deeplabcut_data/toy_model_v2"
    if include_eye:
        eye_video_path = recording_path / "eye_data" / "eye_videos"

        best_eye_model_folder = "/home/scholl-lab/deeplabcut_data/eye_model_v1/eye_model_v1"
        best_mocap_model_folder = "/home/scholl-lab/deeplabcut_data/head_body_eyecam_retrain_test_v2"

        print("Processing eye videos...")
        process_recording(video_folder=eye_video_path, deeplabcut_folder=best_eye_model_folder)
        print("eye videos processed")
    else:
        best_mocap_model_folder = "/home/scholl-lab/deeplabcut_data/head_body_noeyecam_v0"
    print("Processing mocap videos...")
    process_recording(video_folder=mocap_video_path, deeplabcut_folder=best_mocap_model_folder)
    print("mocap videos processed")
    print("Processing mocap videos with toy model...")
    process_recording(video_folder=mocap_video_path, deeplabcut_folder=best_toy_model_folder)
    print("toy model processed")
