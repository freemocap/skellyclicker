import base64
import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from skellyclicker.app.app_state_singleton import get_skellyclicker_app_state
from skellyclicker.models.skellyclicker_types import VideoNameString, JPEGImageString, ImageNumpyArray
import cv2

from skellyclicker.models.video_models import VideoGroupHandler

logger = logging.getLogger(__name__)
videos_router = APIRouter()


class FramesResponse(BaseModel):
    frames: dict[VideoNameString, JPEGImageString] = Field(
        default={},
        description="A dictionary mapping video names to their corresponding JPEG image strings.",
    )
    frame_number: int = Field(
        default=-1,
        ge=-1,
        description="The frame number for the images within their respective videos.",
    )

    @classmethod
    def from_numpy_images(cls, images: dict[VideoNameString, ImageNumpyArray], frame_number: int = -1) -> "FramesResponse":
        """
        Convert a dictionary of numpy images to a FramesResponse object.
        """
        frames = {}
        for video_name, image in images.items():
            # Convert the numpy image to a JPEG string
            frames[video_name] = cls._image_to_jpeg_cv2(image=image)
        return cls(frames=frames, frame_number=frame_number)
    @staticmethod
    def _image_to_jpeg_cv2(image: ImageNumpyArray, quality: int = 90) -> str:
        """
        Convert a numpy array image to a JPEG image using OpenCV.

        """

        # Encode the image as JPEG
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]

        result, jpeg_image = cv2.imencode('.jpg', image, encode_param)

        if not result:
            raise ValueError("Could not encode image to JPEG")
        base64_image = base64.b64encode(jpeg_image).decode('utf-8')
        return base64_image

@videos_router.get("/frames/{frame_number}", response_model=FramesResponse)
def get_frames_by_frame_number(
        frame_number: Annotated[int, Field(ge=0,
                                           default=0,
                                           description="Frame number to retrieve (from all videos).")],) -> FramesResponse:
    """
    Retrieve frames from all videos at the specified frame number.
    """
    logger.info(f"Retrieving frames for frame number: {frame_number}")
    video_group_handler:VideoGroupHandler = get_skellyclicker_app_state().video_group_handler
    if not video_group_handler:
        error_msg = "No video group handler available. Please load a recording first."
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)

    try:
        images = video_group_handler.get_images_by_frame_number(frame_number=frame_number)
        if not images:
            error_msg = f"No images found for frame number: {frame_number}"
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)
        logger.info(f"Retrieved {len(images)} images for frame number: {frame_number}")
        return FramesResponse.from_numpy_images(images=images, frame_number=frame_number)
    except Exception as e:
        error_msg = f"Error retrieving frames: {type(e).__name__} - {str(e)}"
        logger.exception(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
