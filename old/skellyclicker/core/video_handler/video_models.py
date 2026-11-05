from typing import Tuple

import cv2
import math
import numpy as np
from pydantic import BaseModel, ConfigDict

from skellyclicker import VideoPathString


class VideoScalingParameters(BaseModel):
    """Parameters for scaling and positioning video frames in the grid."""

    scale: float
    x_offset: int
    y_offset: int
    scaled_width: int
    scaled_height: int
    original_width: int
    original_height: int


class VideoMetadata(BaseModel):
    """Metadata about a video file."""

    path: str
    name: str
    width: int
    height: int
    frame_count: int


class ZoomState(BaseModel):
    """State of the zoom for a video."""

    scale: float = 1.0
    center_x: int = 0
    center_y: int = 0

    def reset(self):
        self.scale = 1.0
        self.center_x = 0
        self.center_y = 0


class VideoPlaybackState(BaseModel):
    """Current state of video playback."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    metadata: VideoMetadata
    cap: cv2.VideoCapture
    current_frame: np.ndarray | None = None
    processed_frame: np.ndarray | None = None
    scaling_params: VideoScalingParameters | None = (
        None  # rescale info to put it within the grid
    )
    zoom_state: ZoomState = ZoomState()  # how much the user has zoomed in on the video
    contrast: int = 1
    brightness: int = 0

    @property
    def name(self) -> str:
        return self.metadata.name


class ClickData(BaseModel):
    """Data associated with a mouse click."""

    window_x: int
    window_y: int
    video_x: int
    video_y: int
    frame_number: int
    video_index: int

    @property
    def x(self) -> int:
        return int(self.video_x)

    @property
    def y(self) -> int:
        return int(self.video_y)


class GridParameters(BaseModel):
    """Parameters defining the video grid layout."""

    rows: int
    columns: int
    cell_width: int
    cell_height: int
    total_width: int
    total_height: int

    @property
    def cell_size(self) -> Tuple[int, int]:
        return self.cell_width, self.cell_height

    @property
    def grid_size(self) -> Tuple[int, int]:
        return self.rows, self.columns


    @classmethod
    def calculate(
        cls, videos: dict[VideoPathString, VideoPlaybackState], max_window_size: Tuple[int, int]
    ) -> "GridParameters":
        """Calculate grid parameters based on video sizes and window constraints."""
        max_width, max_height = max_window_size
        
        mean_width = sum(video.metadata.width for video in videos.values()) / len(videos)
        mean_height = sum(video.metadata.height for video in videos.values()) / len(videos)

        mean_aspect_ratio = mean_width / mean_height
        
        # make initial estimate
        num_rows = round(math.sqrt(len(videos) * mean_aspect_ratio))
        num_columns = math.ceil(len(videos) / num_rows)
 
        # make sure all videos fit
        while num_rows * num_columns < len(videos):
            if mean_aspect_ratio > 1:
                num_rows += 1
            else:
                num_columns += 1
                
        # remove empty space where possible
        while num_rows * num_columns > len(videos):
            if mean_aspect_ratio < 1: # remove rows first for vertical videos
                if (num_rows - 1) * num_columns >= len(videos):
                    num_rows -= 1
                elif num_rows * (num_columns - 1) >= len(videos):
                    num_columns -= 1
                else:
                    break
            else: # remove columns first for horizontal videos
                if num_rows * (num_columns - 1) >= len(videos):
                    num_columns -= 1
                elif (num_rows - 1) * num_columns >= len(videos):
                    num_rows -= 1
                else:
                    break
    
        # Calculate cell size
        cell_width = max_width // num_columns
        cell_height = max_height // num_rows

        return cls(
            rows=num_rows,
            columns=num_columns,
            cell_width=cell_width,
            cell_height=cell_height,
            total_width=cell_width * num_columns,
            total_height=cell_height * num_rows,
        )