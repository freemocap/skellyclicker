import logging

from fastapi import APIRouter

from skellyclicker.app.skellyclicker_app import get_skellyclicker_app

logger = logging.getLogger(__name__)

dlc_config_router = APIRouter(
    prefix="/config",
    tags=["dlc_config"],
    responses={404: {"description": "Not found"}},
)

@dlc_config_router.get("/iteration", summary="Get current DLC training iteration")
def get_dlc_training_iteration():
    """
    Get the current DLC training iteration.
    
    This endpoint retrieves the current iteration number of the DLC training process.
    """
    logger.api("Retrieving current DLC training iteration")
    try:
        iteration = get_skellyclicker_app().get_dlc_iteration()
    except Exception as e:
        logger.error(f"Failed to retrieve DLC training iteration: {e}")
        return {"error": str(e)}, 500
    logger.api(f"Current DLC training iteration: {iteration}")
    return {"iteration": iteration}

@dlc_config_router.post("/toggle_annotate_videos", summary="toggl whether videos are annotated for DLC training")
def annotate_videos_for_dlc_training():
    """
    Toggle whether videos are annotated during DLC analysis.
    
    This endpoint toggles whether videos are annotated during DLC analysis.
    """
    logger.api("Toggling video annotation for DLC training")
    try:
        get_skellyclicker_app().toggle_annotate_videos()
    except Exception as e:
        logger.error(f"Failed to toggle video annotation for DLC training: {e}")
        return {"error": str(e)}, 500
    logger.api("Video annotation for DLC training toggled successfully")
    return {"message": "Video annotation for DLC training toggled successfully"}

@dlc_config_router.post("/toggle_filter_predictions", summary="Toggle whether to filter predictions during DLC analysis")
def toggle_filter_predictions():
    """
    Toggle whether to filter predictions during DLC analysis.
    
    This endpoint toggles whether predictions are filtered during DLC analysis.
    """
    logger.api("Toggling prediction filtering for DLC analysis")
    try:
        get_skellyclicker_app().toggle_filter_predictions()
    except Exception as e:
        logger.error(f"Failed to toggle prediction filtering for DLC analysis: {e}")
        return {"error": str(e)}, 500
    logger.api("Prediction filtering for DLC analysis toggled successfully")
    return {"message": "Prediction filtering for DLC analysis toggled successfully"}

@dlc_config_router.post("/training_epochs", summary="Set the number of training epochs for DLC")
def set_training_epochs(training_epochs: int):
    """
    Set the number of training epochs for DLC.
    
    This endpoint sets the number of epochs for the DLC training process.
    """
    logger.api(f"Setting DLC training epochs to: {training_epochs}")
    try:
        get_skellyclicker_app().set_training_epochs(training_epochs)
    except Exception as e:
        logger.error(f"Failed to set DLC training epochs: {e}")
        return {"error": str(e)}, 500
    logger.api(f"DLC training epochs set to: {training_epochs}")
    return {"message": "DLC training epochs set successfully", "training_epochs": training_epochs}

@dlc_config_router.post("/set_save_epochs", summary="Set the frequency of epochs to save for DLC")
def set_save_epochs(save_epochs: int):
    """
    Set the frequency of epochs to save for DLC.
    
    This endpoint sets how often the model should be saved during training.
    """
    logger.api(f"Setting DLC save epochs to: {save_epochs}")
    try:
        get_skellyclicker_app().set_training_save_epochs(save_epochs)
    except Exception as e:
        logger.error(f"Failed to set DLC save epochs: {e}")
        return {"error": str(e)}, 500
    logger.api(f"DLC save epochs set to: {save_epochs}")
    return {"message": "DLC save epochs set successfully", "save_epochs": save_epochs}

@dlc_config_router.post("/set_batch_size", summary="Set the batch size for DLC training")
def set_batch_size(batch_size: int):
    """
    Set the batch size for DLC training.
    
    This endpoint sets the batch size used during the training of the DLC model.
    """
    logger.api(f"Setting DLC training batch size to: {batch_size}")
    try:
        get_skellyclicker_app().set_training_batch_size(batch_size)
    except Exception as e:
        logger.error(f"Failed to set DLC training batch size: {e}")
        return {"error": str(e)}, 500
    logger.api(f"DLC training batch size set to: {batch_size}")
    return {"message": "DLC training batch size set successfully", "batch_size": batch_size}