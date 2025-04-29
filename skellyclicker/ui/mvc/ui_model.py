from typing import List
from pydantic import BaseModel


class SkellyClickerUIModel(BaseModel):
    session_saved_path: str | None = None
    csv_saved_path: str | None = None
    machine_labels_path: str | None = None
    is_playing: bool = False
    project_path: str | None = None
    video_files: List[str] | None = None
    auto_save: bool = False
    show_help: bool = False
    current_frame: int = 0
    step_size: int = 1  # Frames to advance per step
    timer_id: int | None = None  # To track the timer for cancellation
    frames_per_second: int = 30  # Default FPS for video playback
    frame_count: int = 0  # Total number of frames in the video
    annotate_videos: bool = False  # To create annotated videos with DLC while analyzing
    tracked_point_names: List[str] | None = None
    training_epochs: int = 200
    training_save_epochs: int = 20
    training_batch_size: int = 1
