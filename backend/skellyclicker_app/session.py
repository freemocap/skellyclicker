"""APP-owned durable navigation state; never starts processing or changes project data."""
import json
import os
from pathlib import Path
from threading import RLock
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from fastapi import APIRouter, HTTPException
from freemocap_sdk.storage import atomic_json

router = APIRouter(prefix="/api/session")
_lock = RLock()

class Session(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    recent_projects: list[str] = Field(default_factory=list)
    project_path: str | None = None
    recording_id: str | None = None
    workspace: Literal["viewer", "training"] = "viewer"
    sidebar: Literal["images", "project"] = "images"
    training_run_id: str | None = None

class SessionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_path: str
    recording_id: str | None = None
    workspace: Literal["viewer", "training"] | None = None
    sidebar: Literal["images", "project"] | None = None
    training_run_id: str | None = None

def session_path():
    override = os.environ.get("SKELLYCLICKER_SESSION_PATH")
    if override:
        return Path(override)
    base = Path(os.environ.get("LOCALAPPDATA", Path.home()/".config"))
    return base/"SkellyClicker"/"session.json"

def read_session():
    path = session_path()
    return Session.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else Session()

def write_session(state):
    path = session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(path, state.model_dump())

def project_history(*paths):
    history = {}
    for path in paths:
        if path:
            history.setdefault(os.path.normcase(path), path)
    return list(history.values())[:30]


@router.get("/recent")
def recent_projects():
    with _lock:
        state = read_session()
        return project_history(state.project_path, *state.recent_projects)


def remember_project(project):
    with _lock:
        state = read_session()
        path = project["manifest_path"]
        ids = [r["recording_id"] for r in project["recordings"]]
        history = project_history(path, state.project_path, *state.recent_projects)
        if state.project_path != path:
            state = Session(project_path=path, workspace=state.workspace, sidebar=state.sidebar)
        if state.recording_id not in ids:
            state = state.model_copy(update={"recording_id": ids[0] if ids else None})
        state.recent_projects = history
        write_session(state)
        return state.model_dump()

@router.get("")
def restore_session():
    from . import project_routes
    from .projects import open_project
    with _lock:
        try:
            state = read_session()
        except (ValueError, OSError) as error:
            return {"state": None, "project": None, "error": f"Cannot read saved session at {session_path()}: {error}"}
        project = None
        error = None
        if state.project_path:
            try:
                project = open_project(Path(state.project_path))
                project_routes.selected = project
            except (ValueError, OSError) as problem:
                error = f"Could not reopen {state.project_path}: {problem}. Open its current location or retry."
        return {"state": state.model_dump(), "project": project, "error": error}

@router.patch("")
def update_session(update: SessionUpdate):
    with _lock:
        try:
            state = read_session()
            if state.project_path != update.project_path:
                raise HTTPException(409, "The active project changed; this session update is stale")
            changes = update.model_dump(exclude_unset=True, exclude={"project_path"})
            changes = {k:v for k,v in changes.items() if v is not None or k in ("recording_id", "training_run_id")}
            state = Session.model_validate({**state.model_dump(), **changes})
            write_session(state)
            return state.model_dump()
        except (ValueError, OSError) as error:
            raise HTTPException(500, f"Could not save session: {error}") from error
