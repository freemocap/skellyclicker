"""Fresh project identities and app-owned manifests; numerical data lives in result files."""
from pathlib import Path
from typing import Literal
from uuid import uuid4
from datetime import datetime, timezone
import json
import shutil
import tempfile

from pydantic import BaseModel, ConfigDict, Field
from freemocap_sdk.recording_structure import RecordingStructure
from freemocap_sdk.storage import atomic_json, file_digest, resolve_relative, project_lock, publish_directory

ID = r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$"

class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Artifact(Model):
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bytes: int = Field(ge=0)

class Stream(Model):
    camera_id: str
    source_view: Literal["left", "right"]
    clock_id: str = "zed-image-clock"
    frame_index: str = "zero-based SVO source frame index"

class Recording(Model):
    schema_version: Literal[1] = 1
    recording_id: str = Field(pattern=ID)
    uuid: str = Field(default_factory=lambda: str(uuid4()))
    source: Artifact
    calibration_source: Artifact
    streams: list[Stream]
    calibration_state: Literal["unqueried", "ready"] = "unqueried"
    input_revision: str | None = None
    # Source config is not rectified playback geometry. Fresh replay supplies that revision.

class Target(Model):
    schema_version: Literal[1] = 1
    object_id: str = Field(pattern=ID)
    uuid: str = Field(default_factory=lambda: str(uuid4()))
    revision: str = "r001"
    type: Literal["rigid_stl"] = "rigid_stl"
    path_basis: Literal["project", "target_directory"] = "project"
    geometry: Artifact
    authored_units: Literal["mm", "m"]
    authored_frame: str = "original STL coordinates"
    authored_geometry: Artifact | None = None
    source_path: str

class Project(Model):
    schema_version: Literal[1] = 1
    project_id: str = Field(pattern=ID)
    uuid: str = Field(default_factory=lambda: str(uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    recording_manifests: list[str]
    target_manifests: list[str]
    sample_result: str | None = None
    playback_result: str | None = None
    label_result: str | None = None
    active_review: str | None = None

class CreateProject(Model):
    project_path: str
    source_svo: str
    calibration_source: str
    source_stl: str
    object_id: str = Field(default="object", pattern=ID)
    authored_units: Literal["mm", "m"] = "mm"

class OpenProject(Model):
    project_path: str


def recording_structure(root: Path, recording_id: str) -> RecordingStructure:
    """The project owns its catalog; the SDK owns every path inside a recording."""
    return RecordingStructure(base_directory=root/'recordings', recording_name=recording_id)


def target_directory(root: Path, recording_id: str, object_id: str, revision: str) -> Path:
    from freemocap_sdk.recording_structure import path_component
    return recording_structure(root, recording_id).application_dir('skellyclicker') / 'inputs' / 'targets' / path_component(object_id) / path_component(revision)


def load_target(root: Path, relative: str) -> Target:
    """Resolve local snapshot references for existing project-level consumers."""
    manifest = resolve_relative(root, relative)
    target = read_model(manifest, Target)
    if target.path_basis == 'project':
        return target
    def normalized(value):
        if value is None: return None
        path = resolve_relative(manifest.parent, value.path)
        return value.model_copy(update={'path': path.relative_to(root).as_posix()})
    return target.model_copy(update={'path_basis': 'project', 'geometry': normalized(target.geometry),
                                     'authored_geometry': normalized(target.authored_geometry)})


def artifact(path: Path, stored_path: str | None = None) -> Artifact:
    if not path.is_file():
        raise ValueError(f"File does not exist: {path}")
    return Artifact(path=stored_path or str(path.resolve()), sha256=file_digest(path), bytes=path.stat().st_size)


def create_project(request: CreateProject) -> dict:
    root = Path(request.project_path).expanduser().resolve()
    if root.exists():
        raise ValueError("Choose a new project folder; existing folders are never overwritten.")
    source = Path(request.source_svo).resolve()
    if source.suffix.lower() != ".svo2":
        raise ValueError("This initial source adapter requires a ZED .svo2 recording.")
    stl = Path(request.source_stl).resolve()
    if stl.suffix.lower() != ".stl":
        raise ValueError("Choose an STL reference geometry.")
    # Validate IDs before creating any directories.
    recording_id = source.parent.name
    recording = Recording(recording_id=recording_id, source=artifact(source),
        calibration_source=artifact(Path(request.calibration_source).resolve()),
        streams=[Stream(camera_id="left", source_view="left"), Stream(camera_id="right", source_view="right")])
    target_folder = target_directory(root, recording_id, request.object_id, "r001").relative_to(root).as_posix()
    target = Target(object_id=request.object_id, authored_units=request.authored_units,
        source_path=str(stl), path_basis="target_directory", geometry=artifact(stl, f"{request.object_id}.stl"))
    project = Project(project_id=root.name,
        recording_manifests=[recording_structure(root,recording_id).stereo_manifest_path.relative_to(root).as_posix()],
        target_manifests=[f"{target_folder}/{request.object_id}_target.json"])
    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{root.name}-pending-", dir=root.parent))
    try:
        geometry = resolve_relative(staging, f"{target_folder}/{target.geometry.path}")
        geometry.parent.mkdir(parents=True)
        shutil.copyfile(stl, geometry)
        if file_digest(geometry) != target.geometry.sha256:
            raise ValueError("Reference geometry changed while creating the project.")
        for name, value in [(project.recording_manifests[0], recording), (project.target_manifests[0], target)]:
            destination = resolve_relative(staging, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            atomic_json(destination, value.model_dump(mode="json"))
        atomic_json(staging / f"{project.project_id}_project.json", project.model_dump(mode="json"))
        with project_lock(root.parent):
            publish_directory(staging=staging, destination=root)
    finally:
        # Only our unique, checked staging directory; never user source/project data.
        if staging.exists():
            shutil.rmtree(staging)
    return open_project(root)


def read_model(path: Path, model):
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def open_project(path: Path) -> dict:
    selected = path.expanduser().resolve()
    if selected.is_file():
        manifest = selected
        root = selected.parent
    else:
        root = selected
        candidates = list(root.glob("*_project.json"))
        if len(candidates) != 1:
            raise ValueError("Select the exact *_project.json file when a folder has zero or multiple project manifests.")
        manifest = candidates[0]
    project = read_model(manifest, Project)
    if manifest.name != f"{project.project_id}_project.json":
        raise ValueError("Project manifest filename must match its stored project ID.")
    recordings = [read_model(resolve_relative(root, name), Recording) for name in project.recording_manifests]
    targets = [load_target(root, name) for name in project.target_manifests]
    issues = []
    for recording in recordings:
        for kind, value in [("source", recording.source), ("calibration source", recording.calibration_source)]:
            source = Path(value.path)
            if not source.is_file():
                issues.append(f"Missing {kind}: {source}")
            elif source.stat().st_size != value.bytes or file_digest(source) != value.sha256:
                issues.append(f"Changed {kind}: {source}; relink/verify before using it.")
    for target in targets:
        geometry = resolve_relative(root, target.geometry.path)
        if not geometry.is_file() or file_digest(geometry) != target.geometry.sha256:
            issues.append(f"Missing or changed target geometry: {target.object_id}")
    from .playback_adapter import register_project
    playback = register_project(root, project)
    return {"root": str(root), "manifest_path": str(manifest), "project": project.model_dump(mode="json"),
        "recordings": [r.model_dump(mode="json") for r in recordings],
        "targets": [t.model_dump(mode="json") for t in targets], "issues": issues,
        "sample_state": "prepared" if project.sample_result else "not_prepared", "playback": playback}
