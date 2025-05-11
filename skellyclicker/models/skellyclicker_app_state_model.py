from pydantic import BaseModel
import multiprocessing

from skellyclicker.models.video_models import VideoGroupHandler


class SkellyClickerAppState(BaseModel):
    video_group_handler: VideoGroupHandler| None = None

    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value):
        return cls()

    def close(self):
        """Release any resources held by the app state."""
        if self.video_group_handler:
            self.video_group_handler.close()
            self.video_group_handler = None

    def set_recording_path(self, recording_path: str) -> None:
        """Set the recording path and load the video group handler."""
        self.video_group_handler = VideoGroupHandler.from_recording_path(recording_path)