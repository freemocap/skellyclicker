import logging

from fastapi import APIRouter

from skellyclicker.api.http.dlc_router.dlc_config_router import dlc_config_router
from skellyclicker.api.http.dlc_router.dlc_project_router import dlc_project_router
from skellyclicker.app.skellyclicker_app import get_skellyclicker_app

logger = logging.getLogger(__name__)

dlc_router = APIRouter(
    prefix="/dlc",
    tags=["dlc"],
    responses={404: {"description": "Not found"}},
)

dlc_router.include_router(dlc_project_router)
dlc_router.include_router(dlc_config_router)

@dlc_router.post("/train", summary="Train a DLC model")
def train_dlc_model():
    """
    Train a DeepLabCut model.
    
    This endpoint triggers the training of a DLC model using the current configuration.
    """
    logger.api("Starting DLC model training")
    try:
        get_skellyclicker_app().train_model()
    except Exception as e:
        logger.error(f"Failed to train DLC model: {e}")
        return {"error": str(e)}, 500
    logger.api("DLC model training completed successfully")
    return {"message": "DLC model training completed successfully"}

@dlc_router.post("/analyze_videos", summary="Analyze videos with the DLC model")
def analyze_videos(video_paths: list[str], copy_to_machine_labels: bool = False):
    """
    Analyze videos using the trained DLC model.
    
    This endpoint processes the videos with the trained DLC model to generate predictions.

    Copy to machine labels uses the DLC predictions to visualize machine outputs in the clicking UI.
    """
    logger.api("Starting video analysis with DLC model")
    try:
        get_skellyclicker_app().analyze_videos(video_paths=video_paths, copy_to_machine_labels=copy_to_machine_labels)
    except Exception as e:
        logger.error(f"Failed to analyze videos with DLC model: {e}")
        return {"error": str(e)}, 500
    logger.api("Video analysis with DLC model completed successfully")
    return {"message": "Video analysis with DLC model completed successfully"}


@dlc_router.post("/analyze_training_videos", summary="Analyze the training videos with the DLC model")
def analyze_training_videos():
    """
    Analyze the training videos using the trained DLC model.
    
    This endpoint processes the training videos with the trained DLC model to generate predictions.

    Copies the machine labels to the clicking UI for visualization.
    """
    logger.api("Starting analysis of training videos with DLC model")
    try:
        get_skellyclicker_app().analyze_training_videos()
    except Exception as e:
        logger.error(f"Failed to analyze training videos with DLC model: {e}")
        return {"error": str(e)}, 500
    logger.api("Analysis of training videos with DLC model completed successfully")
    return {"message": "Analysis of training videos with DLC model completed successfully"}