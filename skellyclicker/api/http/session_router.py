import logging

from fastapi import APIRouter

from skellyclicker.app.skellyclicker_app import get_skellyclicker_app

logger = logging.getLogger(__name__)

session_router = APIRouter(
    prefix="/session",
    tags=["session"],
    responses={404: {"description": "Not found"}},
)

@session_router.post("/save", summary="Save current session")
def save_session(output_path: str):
    """
    Save the current session of the SkellyClicker application.
    
    This endpoint saves the current state of the application, including loaded videos and labels.
    """
    logger.api("Saving current session")
    try:
        get_skellyclicker_app().save_session(output_path=output_path)
    except Exception as e:
        logger.error(f"Failed to save session: {e}")
        return {"error": str(e)}, 500
    logger.api("Session saved successfully")
    return {"message": "Session saved successfully"}

@session_router.post("/load", summary="Load a saved session")
def load_session(input_path: str):
    """
    Load a saved session into the SkellyClicker application.
    
    This endpoint loads the state of the application from a previously saved session file.
    """
    logger.api(f"Loading session from: {input_path}")
    try:
        get_skellyclicker_app().load_session(json_file=input_path)
    except Exception as e:
        logger.error(f"Failed to load session: {e}")
        return {"error": str(e)}, 500
    logger.api("Session loaded successfully")
    return {"message": "Session loaded successfully", "input_path": input_path}

@session_router.post("/clear", summary="Clear current session")
def clear_session():
    """
    Clear the current session of the SkellyClicker application.
    
    This endpoint clears all loaded videos and labels, resetting the application state.
    """
    logger.api("Clearing current session")
    try:
        get_skellyclicker_app().clear_session()
    except Exception as e:
        logger.error(f"Failed to clear session: {e}")
        return {"error": str(e)}, 500
    logger.api("Session cleared successfully")
    return {"message": "Session cleared successfully"}

@session_router.post("/toggle_auto_save", summary="Toggle auto-save feature")
def toggle_auto_save():
    """
    Toggle the auto-save feature of the SkellyClicker application.
    
    This endpoint enables or disables the auto-save functionality, which automatically saves the session on application close.
    """
    logger.api("Toggling auto-save session")
    try:
        get_skellyclicker_app().toggle_autosave()
    except Exception as e:
        logger.error(f"Failed to toggle auto-save: {e}")
        return {"error": str(e)}, 500
    logger.api("Auto-save toggled successfully")
    return {"message": "Auto-save toggled successfully"}