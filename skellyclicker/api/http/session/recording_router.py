import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, DirectoryPath, Field

from skellyclicker.app.app_state_singleton import SkellyClickerAppState, get_skellyclicker_app_state

logger = logging.getLogger(__name__)
session_router = APIRouter()

DEFAULT_RECORDING_PATH = str(Path.home() / "freemocap_data" / "recording_sessions" / "freemocap_test_data")

class LoadRecordingRequest(BaseModel):
    recording_path: str = Field(default=DEFAULT_RECORDING_PATH, description="Path to the recording directory, which should contain a folder called `synchronized_videos` with the video files.")

class LoadRecordingResponse(BaseModel):
    recording_path: str = Field(default=DEFAULT_RECORDING_PATH, description="Path to the recording directory, which should contain a folder called `synchronized_videos` with the video files.")
    recording_name: str | None = Field(default=None, description="Name of the recording session, derived from the directory name.")
    video_paths: list[str] = Field(default=[], description="List of video paths in the recording session.")
    frame_count: int = Field(default=0, ge=0, description="Total number of frames across all videos in the recording session.")
    @classmethod
    def from_app_state(cls, app_state: SkellyClickerAppState) -> "LoadRecordingResponse":
        return cls(
            recording_path=app_state.recording_path,
            recording_name=app_state.recording_name,
            video_paths=[str(video_path) for video_path in app_state.video_group_handler.video_paths],
            frame_count=app_state.video_group_handler.frame_count if app_state.video_group_handler else 0,
        )

@session_router.post("/load_recording", response_model=LoadRecordingResponse)
async def load_recording_endpoint(request: LoadRecordingRequest = Body(..., description="Request body containing the path to the recording directory",
                                                                       examples=[LoadRecordingRequest()])
                                  ) -> LoadRecordingResponse:
    logger.info(f"Loading recording from path: {request.recording_path}")
    if not Path(request.recording_path).is_dir():
        error_msg = f"Recording path does not exist or is not a directory: {request.recording_path}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    try:
        get_skellyclicker_app_state().set_recording_path(str(request.recording_path))
        return LoadRecordingResponse.from_app_state(get_skellyclicker_app_state())
    except ValueError as e:
        error_msg = f"Invalid recording path: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_msg = f"Failed to load recording: {type(e).__name__} - {str(e)}"
        logger.exception(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


