"""App project selection; SDK owns server lifecycle and storage primitives."""
from pathlib import Path
import logging
from fastapi import APIRouter, HTTPException
from .projects import CreateProject, OpenProject, create_project, open_project

router = APIRouter(prefix="/api/projects")
selected: dict | None = None
logger = logging.getLogger("skellyclicker.projects")

@router.get("/selected")
def get_selected():
    return selected

@router.post("/create")
def create(request: CreateProject):
    global selected
    try:
        logger.info("Creating fresh project at %s", request.project_path)
        selected = create_project(request)
        logger.info("Created project %s with linked original media and target snapshot", selected["project"]["project_id"])
        return selected
    except (ValueError, OSError) as error:
        logger.warning("Project operation failed: %s", error)
        raise HTTPException(status_code=400, detail=str(error)) from error

@router.post("/open")
def open_existing(request: OpenProject):
    global selected
    try:
        logger.info("Opening project %s", request.project_path)
        selected = open_project(Path(request.project_path))
        logger.info("Opened project %s: %d recording(s), %d target(s)", selected["project"]["project_id"], len(selected["recordings"]), len(selected["targets"]))
        for issue in selected["issues"]:
            logger.warning("Project input unavailable: %s", issue)
        return selected
    except (ValueError, OSError) as error:
        logger.warning("Project operation failed: %s", error)
        raise HTTPException(status_code=400, detail=str(error)) from error

