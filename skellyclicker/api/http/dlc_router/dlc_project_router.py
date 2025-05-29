import logging

from fastapi import APIRouter

from skellyclicker.app.skellyclicker_app import get_skellyclicker_app

logger = logging.getLogger(__name__)

dlc_project_router = APIRouter(
    prefix="/project",
    tags=["dlc_project"],
    responses={404: {"description": "Not found"}},
)

@dlc_project_router.post("/create", summary="Create new DLC project")
def create_dlc_project(project_name: str, project_path: str):
    """
    Create a new DeepLabCut project.

    This endpoint creates a new DLC project with the specified name and path.
    """
    logger.api(f"Creating new DLC project: {project_name} at {project_path}")
    try:
        get_skellyclicker_app().create_deeplabcut_project(project_name=project_name, project_path=project_path)
    except Exception as e:
        logger.error(f"Failed to create DLC project: {e}")
        return {"error": str(e)}, 500
    logger.api("DLC project created successfully")
    return {"message": "DLC project created successfully", "project_name": project_name, "project_path": project_path}

@dlc_project_router.post("/load", summary="Load DLC project")
def load_dlc_project(input_path: str):
    """
    Load a DLC project from the specified input path.

    This endpoint loads a DLC project into the SkellyClicker application.
    """
    logger.api(f"Loading DLC project from: {input_path}")
    try:
        get_skellyclicker_app().load_deeplabcut_project(project_path=input_path)
    except Exception as e:
        logger.error(f"Failed to load DLC project: {e}")
        return {"error": str(e)}, 500
    logger.api("DLC project loaded successfully")
    return {"message": "DLC project loaded successfully", "input_path": input_path}

