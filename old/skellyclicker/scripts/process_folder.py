import shutil
import sys
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

def clean_dlc_output_folder(dlc_output_folder: Path):
    if not dlc_output_folder.exists() or not dlc_output_folder.is_dir():
        return
    print("Existing dlc data found, removing it to ensure latest model is used")
    patterns = ["*snapshot*.csv", "*snapshot*.h5", "*snapshot*.pickle"]
    for pattern in patterns:
        for file in dlc_output_folder.glob(pattern):
            print(f"Removing existinng file {file}")
            file.unlink()

def process_folder(video_folder: Path, deeplabcut_folder: Path | str, output_folder: Path | None = None, suffix: str = ""):
    if output_folder is None:
        output_folder = video_folder.parent
    deeplabcut_folder = Path(deeplabcut_folder)
    dlc_output_folder = output_folder / "dlc_output"
    annotated_videos_folder = output_folder / "annotated_videos" / f"annotated_videos_{deeplabcut_folder.stem}{suffix}"
    dlc_output_folder.mkdir(exist_ok=True, parents=True)
    annotated_videos_folder.mkdir(exist_ok=True, parents=True)
    analyze_videos_output = dlc_output_folder / f"{deeplabcut_folder.stem}{suffix}"
    clean_dlc_output_folder(analyze_videos_output)
    deeplabcut_config = deeplabcut_folder / "config.yaml"
    handler = DeeplabcutHandler.load_deeplabcut_project(project_config_path=str(deeplabcut_config))
    video_paths = [str(path) for path in video_folder.glob("*.mp4")]
    print(f"VIDEO PATHS in {video_folder}: \n{video_paths}")
    handler.analyze_videos(video_paths=video_paths, output_folder=analyze_videos_output, annotate_videos=True, filter_videos=True)

    annotated_video_paths = list(analyze_videos_output.glob("*.mp4"))
    copy_files(files = annotated_video_paths, destination=annotated_videos_folder)

if __name__=="__main__":
    # use /full_recording or /clips/{clip_name}
    recording_path = Path("/home/scholl-lab/ferret_recordings/session_2025-07-09_ferret_753_EyeCameras_P41_E13/full_recording")
    deeplabcut_path = "/home/scholl-lab/skellyclicker/error_measurement_model/error_measurement_model"

    if len(sys.argv) >= 2:
        recording_folder = Path(sys.argv[1])
    else:
        recording_folder = recording_path
        print(f"Using default directory: {recording_folder}")

    if len(sys.argv) >= 3:
        deeplabcut_folder = sys.argv[2]
        print(f"Using deeplabcut folder: {deeplabcut_folder}")
    else:
        deeplabcut_folder = deeplabcut_path
        print(f"Using default deeplabcut folder: {deeplabcut_folder}")

    if not recording_folder.exists():
        print(f"Error: Directory does not exist: {recording_folder}")
        print("\nUsage: python process_recording.py [recording_folder] {--skip-eye | -e} {--skip-body | -b} {--skip-toy | -t}")
        sys.exit(1)

    flags = [a for a in sys.argv[1:] if a.startswith("-")]

    # Process boolean flags
    for flag in flags:
        print(f"Warning: unknown flag {flag}")

    process_folder(
        video_folder=recording_folder / "mocap_data" / "synchronized_corrected_videos",
        deeplabcut_folder=deeplabcut_folder,
    )
