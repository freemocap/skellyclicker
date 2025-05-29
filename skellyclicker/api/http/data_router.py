import logging

from fastapi import APIRouter

from skellyclicker.app.skellyclicker_app import get_skellyclicker_app

logger = logging.getLogger(__name__)

data_router = APIRouter(
    prefix="/data",
    tags=["data"],
    responses={404: {"description": "Not found"}},
)

@data_router.post("/load_clicks", summary="Load click data")
def load_click_data(file_path: str):
    """
    Load click data from the specified file path.
    
    This endpoint accepts a file path and loads click data into the application.
    """
    logger.api(f"Loading click data from: {file_path}")
    try:
        get_skellyclicker_app().load_labels_csv(file_path)
    except Exception as e:
        logger.error(f"Failed to load click data: {e}")
        return {"error": str(e)}, 500
    logger.api(f"Click data loaded successfully from: {file_path}")
    return {"message": "Click data loaded successfully", "file_path": file_path}

@data_router.post("/clear_clicks", summary="Clear click data")
def clear_click_data():
    """
    Clear all click data from the application.
    
    This endpoint clears all loaded click data.
    """
    logger.api("Clearing all click data")
    try:
        get_skellyclicker_app().clear_labels_csv()
    except Exception as e:
        logger.error(f"Failed to clear click data: {e}")
        return {"error": str(e)}, 500
    logger.api("Click data cleared successfully")
    return {"message": "Click data cleared successfully"}

@data_router.post("/load_machine_labels", summary="Load machine labels")
def load_machine_labels(file_path: str):
    """
    Load machine labels from the specified file path.
    
    This endpoint accepts a file path and loads machine labels into the application.
    """
    logger.api(f"Loading machine labels from: {file_path}")
    try:
        get_skellyclicker_app().load_machine_labels_csv(file_path)
    except Exception as e:
        logger.error(f"Failed to load machine labels: {e}")
        return {"error": str(e)}, 500
    logger.api(f"Machine labels loaded successfully from: {file_path}")
    return {"message": "Machine labels loaded successfully", "file_path": file_path}

@data_router.post("/clear_machine_labels", summary="Clear machine labels")
def clear_machine_labels():
    """
    Clear all machine labels from the application.
    
    This endpoint clears all loaded machine labels.
    """
    logger.api("Clearing all machine labels")
    try:
        get_skellyclicker_app().clear_machine_labels_csv()
    except Exception as e:
        logger.error(f"Failed to clear machine labels: {e}")
        return {"error": str(e)}, 500
    logger.api("Machine labels cleared successfully")
    return {"message": "Machine labels cleared successfully"}
