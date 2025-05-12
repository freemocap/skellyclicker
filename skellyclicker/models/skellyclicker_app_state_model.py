from pathlib import Path

from pydantic import BaseModel
import multiprocessing

from skellyclicker.models.video_models import VideoGroupHandler


class SkellyClickerAppState(BaseModel):
    recording_path: str | None = None
    current_frame_number: int = -1
    video_group_handler: VideoGroupHandler| None = None

    def set_current_frame_number(self, value: int) -> None:
        if not isinstance(value, int):
            raise ValueError("current_frame_number must be an integer")
        if value < 0:
            raise ValueError("current_frame_number must be non-negative")
        if self.video_group_handler and value >= self.video_group_handler.total_frame_count:
            raise ValueError("current_frame_number exceeds total frame count")
        self.current_frame_number = value

    @property
    def recording_name(self) -> str | None:
        """Get the name of the recording without the file extension."""
        if self.recording_path:
            return Path(self.recording_path).name
        return None


    @property
    def total_frame_count(self) -> int | None:
        """Get the total frame count of the recording."""
        if self.video_group_handler:
            return self.video_group_handler.total_frame_count
        return None

    def close(self):
        """Release any resources held by the app state."""
        if self.video_group_handler:
            self.video_group_handler.close()
            self.video_group_handler = None

    def set_recording_path(self, recording_path: str) -> None:
        """Set the recording path and load the video group handler."""
        self.video_group_handler = VideoGroupHandler.from_recording_path(recording_path)
        self.recording_path = recording_path