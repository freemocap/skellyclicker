import math
from pathlib import Path

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict

from skellyclicker import VideoPathString, VideoNameString, MAX_WINDOW_SIZE


class VideoMetadata(BaseModel):
    """Metadata about a video file."""

    path: VideoPathString
    name: VideoNameString
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

class VideoGridScalingParameters(BaseModel):
    """Parameters for scaling and positioning video frames in the grid."""
    scale: float
    grid_index: int  # index of the video in the grid
    x_offset: int # offset from the left edge of the cell
    y_offset: int # offset from the top edge of the cell
    scaled_width: int # width of the video in the grid
    scaled_height: int # height of the video in the grid
    cell_row: int = 0  # row in the grid where the video is displayed
    cell_column: int = 0  # column in the grid where the video is displayed
    cell_height: int = 0  # height of the cell in the grid
    cell_width: int = 0  # width of the cell in the grid

    @property
    def x_start(self) -> int: # x position of the video in the grid
        return int(self.cell_column * self.cell_width + self.x_offset)

    @property
    def y_start(self) -> int: # y position of the video in the grid
        return int(self.cell_row * self.cell_height + self.y_offset)

class VideoPlaybackObject(BaseModel):
    """Current state of video playback."""

    cap: cv2.VideoCapture
    metadata: VideoMetadata

    current_frame: np.ndarray | None = None
    processed_frame: np.ndarray | None = None

    grid_scale: VideoGridScalingParameters | None = None
    zoom_state: ZoomState = ZoomState()  # how much the user has zoomed in on the video

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def get_frame(self, frame_number: int):
        """Get a specific frame from the video."""
        if not self.cap.isOpened():
            raise ValueError(f"Video {self.metadata.name} is not opened.")
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        success, frame = self.cap.read()
        if success:
            self.current_frame = frame
            return frame
        else:
            raise ValueError(f"Could not read frame {frame_number} from video {self.metadata.name}.")

    @classmethod
    def from_file(cls, path: VideoPathString) -> "VideoPlaybackObject":
        if not Path(path).is_file():
            raise ValueError(f"File {path} does not exist.")
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {path}")
        success, image = cap.read()
        if not success:
            raise ValueError(f"Could not read video: {path}")
        return cls(
            cap=cap,
            current_frame=image,
            metadata=VideoMetadata(
                path=path,
                name=Path(path).stem,
                width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                frame_count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            ))

    @property
    def name(self) -> str:
        return self.metadata.name




class VideoGridHelper(BaseModel):
    """Parameters defining the video grid layout."""
    rows: int
    columns: int
    cell_width: int
    cell_height: int
    total_width: int
    total_height: int

    @property
    def cell_size(self) -> tuple[int, int]:
        return self.cell_width, self.cell_height

    @property
    def grid_size(self) -> tuple[int, int]:
        return self.rows, self.columns

    def get_row_by_index(self, index: int):
        """Get the row index for a given video index."""
        return index // self.columns

    def get_column_by_index(self, index: int):
        """Get the column index for a given video index."""
        return index % self.columns

    @classmethod
    def calculate(cls,
                  videos: dict[VideoNameString, VideoPlaybackObject],
                  max_window_size: tuple[int, int] = MAX_WINDOW_SIZE
                  ) -> "VideoGridHelper":
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
            if mean_aspect_ratio < 1:  # remove rows first for vertical videos
                if (num_rows - 1) * num_columns >= len(videos):
                    num_rows -= 1
                elif num_rows * (num_columns - 1) >= len(videos):
                    num_columns -= 1
                else:
                    break
            else:  # remove columns first for horizontal videos
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

    def create_blank_grid_image(self) -> np.ndarray:
        grid_image = np.zeros((self.total_height,
                               self.total_width,
                               3), dtype=np.uint8)

        # sete the elements along cell edges to 1
        grid_image[::self.cell_height, :] = 1
        grid_image[:, ::self.cell_width] = 1
        return grid_image

