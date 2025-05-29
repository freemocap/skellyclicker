import logging
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

from skellyclicker.app.skellyclicker_app import get_skellyclicker_app
from skellyclicker.system.files_and_folder_names import FREEMOCAP_SAMPLE_DATA_PATH

logger = logging.getLogger(__name__)

video_router = APIRouter(
    prefix="/video",
    tags=["video_control"],
    responses={404: {"description": "Not found"}},
)

class VideoPaths(BaseModel):
    paths: list[str]

@video_router.post("/load", summary="Load video files")
def load_videos(video_paths: VideoPaths = VideoPaths(paths=[str(path) for path in FREEMOCAP_SAMPLE_DATA_PATH.glob("*.mp4")])):
    """
    Load video files from the provided paths.

    This endpoint accepts a list of video file paths and loads them into the application.
    """
    logger.api(f"Loading videos from paths: {video_paths.paths}")
    try:
        get_skellyclicker_app().load_videos(video_paths.paths)
    except Exception as e:
        logger.error(f"Failed to load videos: {e}")
        return {"error": str(e)}, 500
    logger.api(f"Videos loaded successfully: {video_paths.paths}")
    return {"message": "Videos loaded successfully", "paths": video_paths.paths}

@video_router.post("/open", summary="Open video files")
def open_videos():
    """
    Open most recently loaded video files.
    """
    logger.api(f"Opening most recently loaded videos")
    try:
        get_skellyclicker_app().open_videos()
    except Exception as e:
        logger.error(f"Failed to open videos: {e}")
        return {"error": str(e)}, 500
    logger.api(f"Videos opened successfully")
    return {"message": "Videos opened successfully"}
