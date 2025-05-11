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

@session_router.post("/load_recording", response_model=SkellyClickerAppState)
async def load_recording_endpoint(request: LoadRecordingRequest = Body(..., description="Request body containing the path to the recording directory",
                                                                       examples=[LoadRecordingRequest()])
                                  ) -> SkellyClickerAppState:
    logger.info(f"Loading recording from path: {request.recording_path}")
    if not Path(request.recording_path).is_dir():
        error_msg = f"Recording path does not exist or is not a directory: {request.recording_path}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    try:
        get_skellyclicker_app_state().set_recording_path(str(request.recording_path))
        return get_skellyclicker_app_state()
    except ValueError as e:
        error_msg = f"Invalid recording path: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_msg = f"Failed to load recording: {type(e).__name__} - {str(e)}"
        logger.exception(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)