import logging
import mimetypes
from pathlib import Path
from typing import Annotated

import cv2
from pydantic import BaseModel, Field, BeforeValidator, field_validator

from skellyclicker.models.skellyclicker_types import ImageNumpyArray, FrameNumberInt, VideoNameString

logger = logging.getLogger(__name__)

CV2_COMPATIBLE_VIDEO_FILE_EXTENSIONS = ['.mp4', '.avi', '.mov', '.wmv']

def validate_file_exists(path: str ) -> str:
    """Validate that a file exists at the given path."""
    path_obj = Path(path)
    if not path_obj.is_file():
        raise ValueError(f"File does not exist: {path}")
    return str(path_obj)

def validate_is_video(path: str) -> str:
    """Validate that the file at the given path is a video file."""
    mime_type, _ = mimetypes.guess_type(path)
    path = Path(path)
    if not mime_type or not mime_type.startswith('video/'):
        if not any(path.name.lower().endswith(ext) for ext in CV2_COMPATIBLE_VIDEO_FILE_EXTENSIONS):
            raise ValueError(f"File is not a recognized video format: {path}")
    return str(path)



class ClickData(BaseModel):
    x: int
    y: int
    frame_number: int

VIDEO_CAPTURE_OBJECTS: dict[VideoNameString, cv2.VideoCapture] = {}
def get_video_capture_object(video_name: VideoNameString) -> cv2.VideoCapture:
    """Get a video capture object for the given video path."""
    if video_name not in VIDEO_CAPTURE_OBJECTS:
        raise ValueError(f"Video capture object not found for video: {video_name}")
    if VIDEO_CAPTURE_OBJECTS[video_name] is None or not VIDEO_CAPTURE_OBJECTS[video_name].isOpened():
        raise ValueError(f"Video capture object is not opened for video: {video_name}")
    return VIDEO_CAPTURE_OBJECTS[video_name]

def set_video_capture_object(video_path: str) -> None:
    """Set a video capture object for the given video path."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Failed to open video file: {video_path}")
    success, image = cap.read()
    if not success:
        raise ValueError(f"Failed to read first frame from video file: {video_path}")
    if image is None:
        raise ValueError(f"First frame is None for video file: {video_path}")
    video_name = Path(video_path).name

    if video_path in VIDEO_CAPTURE_OBJECTS:
        VIDEO_CAPTURE_OBJECTS[video_name].release()
    VIDEO_CAPTURE_OBJECTS[video_name] = cap


class VideoHandler(BaseModel):
    """Current state of video playback."""
    path: Annotated[str, BeforeValidator(validate_file_exists), BeforeValidator(validate_is_video)]
    clicks: dict[FrameNumberInt, ClickData] = Field(default_factory=dict)

    @classmethod
    def load_video(cls, video_path: str) -> 'VideoHandler':
        """Load a video file and return its metadata and capture object."""
        set_video_capture_object(video_path=video_path)
        return cls(path=video_path)

    @property
    def cap(self) -> cv2.VideoCapture:
        """Get the video capture object for the video."""
        return get_video_capture_object(self.name)

    @property
    def name(self) -> VideoNameString:
        return Path(self.path).name

    @property
    def frame_count(self) -> int:
        return int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

    @property
    def width(self) -> int:
        return int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    @property
    def height(self) -> int:
        return int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def close(self):
        """Release the video capture object."""
        if self.cap is not None:
            self.cap.release()

        logger.info(f"Video capture object for {self.path} released.")

    def get_frame(self, frame_number: FrameNumberInt) -> ImageNumpyArray | None:
        """Get the specified frame from the video."""
        if self.cap is None:
            logger.error("Video capture object is not initialized.")
            raise ValueError("Video capture object is not initialized.")
        if frame_number < 0 or frame_number >= self.frame_count:
            logger.error(f"Frame number {frame_number} is out of bounds for video {self.path}")
            raise ValueError(f"Frame number {frame_number} is out of bounds for video {self.path}")
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.cap.read()
        if ret:
            return frame
        else:
            logger.error(f"Failed to read frame {frame_number} from video {self.path}")
            raise ValueError(f"Failed to read frame {frame_number} from video {self.path}")

    def add_click_data(self, frame_number: FrameNumberInt, x: int, y: int) -> None:
        """Add click data for a specific frame."""
        if self.cap is None:
            logger.error("Video capture object is not initialized.")
            raise ValueError("Video capture object is not initialized.")
        if frame_number < 0 or frame_number >= self.frame_count:
            logger.error(f"Frame number {frame_number} is out of bounds for video {self.path}")
            raise ValueError(f"Frame number {frame_number} is out of bounds for video {self.path}")
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            logger.error(f"Click coordinates ({x}, {y}) are out of bounds for video {self.path} with size ({self.width}, {self.height})")
            raise ValueError(f"Click coordinates ({x}, {y}) are out of bounds for video {self.path} with size ({self.width}, {self.height})")

        if frame_number not in self.clicks:
            self.clicks[frame_number] = ClickData(x=x, y=y, frame_number=frame_number)
        else:
            logger.warning(f"Click data for frame {frame_number} already exists. Overwriting.")
            self.clicks[frame_number].x = x
            self.clicks[frame_number].y = y

class VideoGroupHandler(BaseModel):
    """Handles multiple video files and their metadata."""
    videos: dict[VideoNameString, VideoHandler] = Field(default_factory=dict)

    @property
    def video_paths(self) -> list[str]:
        """Get the paths of all videos in the group."""
        return [video.path for video in self.videos.values()]

    @property
    def frame_count(self) -> int:
        """Get the total frame count of all videos in the group."""
        if not self.videos:
            return 0
        frame_count = set([video.frame_count for video in self.videos.values()])
        if len(frame_count) > 1:
            logger.error("All videos must have the same number of frames.")
            raise ValueError("All videos must have the same number of frames.")
        return frame_count.pop()

    @classmethod
    def from_recording_path(cls, recording_path: str):
        """Create a VideoGroupHandler from a recording path
         Assumes there is a folder called `synchronized_videos`, which contains synchronized videos
         with precisely the same number of frames"""

        synchronized_videos_folder = Path(recording_path) / 'synchronized_videos'
        if not synchronized_videos_folder.is_dir():
            logger.error(f"Synchronized videos folder does not exist: {synchronized_videos_folder}")
            raise ValueError(f"Synchronized videos folder does not exist: {synchronized_videos_folder}")
        return cls.from_video_folder(str(synchronized_videos_folder))

    @classmethod
    def from_paths(cls, video_paths: list[str]) -> 'VideoGroupHandler':
        """Create a VideoGroupHandler from a list of video paths."""
        videos = {}
        for path in video_paths:
            video_handler = VideoHandler.load_video(path)
            videos[video_handler.name] = video_handler
        return cls(videos=videos)

    @classmethod
    def from_video_folder(cls, video_folder: str) -> 'VideoGroupHandler':
        """Create a VideoGroupHandler from a folder containing video files."""
        video_paths = [str(path) for path in Path(video_folder).glob('*') if path.is_file() and path.suffix in CV2_COMPATIBLE_VIDEO_FILE_EXTENSIONS]
        return cls.from_paths(video_paths)

    @field_validator('videos', mode='before')
    def validate_frame_counts_equal(cls, value: dict[VideoNameString, VideoHandler]) -> dict[VideoNameString, VideoHandler]:
        """Ensure all videos have the same number of frames."""
        frame_counts = {name: video.frame_count for name, video in value.items()}
        if len(set(frame_counts.values())) > 1:
            raise ValueError("All videos must have the same number of frames.")
        return value

    def get_images_by_frame_number(self, frame_number: FrameNumberInt) -> dict[VideoNameString, ImageNumpyArray]:
        """Get the specified frame from all videos."""
        frames = {}
        for name, video in self.videos.items():
            frame = video.get_frame(frame_number)
            if frame is not None:
                frames[name] = frame
            else:
                logger.error(f"Failed to read frame {frame_number} from video {name}")
        return frames

    def add_click_data(self, video_name:VideoNameString, frame_number: FrameNumberInt, x: int, y: int) -> None:
        """Add click data for a specific video and frame."""
        if video_name not in self.videos:
            logger.error(f"Video {video_name} not found in VideoGroupHandler.")
            raise ValueError(f"Video {video_name} not found in VideoGroupHandler.")
        self.videos[video_name].add_click_data(frame_number, x, y)

    def close(self):
        """Release all video capture objects."""
        for video in self.videos.values():
            video.close()
        self.videos.clear()
        logger.info("VideoGroupHandler closed and all videos released.")