"""Open synchronized source media directly and persist recording-local manual observations."""
from pathlib import Path
from threading import RLock
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from skellycam.core.recorders.videos.video_file_metadata import VideoFileMetadata
from freemocap_sdk.storage import atomic_json
from freemocap.api.http.playback import playback_router as playback
from freemocap.api.http.recordings.recording_access import RecordingReadRoute
from freemocap.core.playback.media_selection import PlaybackVideoSource, discover_video_paths, video_source_folder

router = APIRouter(prefix="/api")
resources = APIRouter(route_class=RecordingReadRoute)
_lock = RLock()
_sources: dict[tuple[str, str], Path] = {}


def register_label_source(root: Path, directory: Path):
    parent = str(root.parent)
    _sources[root.name, parent] = directory
    return {"id": root.name, "parent": parent}


def has_videos(root):
    folder = video_source_folder(recording=root, source=PlaybackVideoSource.SYNCHRONIZED)
    return root.is_dir() and bool(discover_video_paths(folder=folder))


def open_recording(root):
    root = root.resolve(strict=True)
    if root.name == "synchronized_videos":
        root = root.parent
    elif root.name == "synchronized" and root.parent.name == "videos":
        root = root.parent.parent
    if not has_videos(root):
        children = [{"name": p.name, "path": str(p)} for p in sorted(root.iterdir()) if p.is_dir() and has_videos(p)]
        if children:
            return {"candidates": children}
        raise ValueError("Choose a FreeMoCap recording or its parent folder.")
    folder = video_source_folder(recording=root, source=PlaybackVideoSource.SYNCHRONIZED)
    sizes = {path.name: [info.width,info.height] for path in discover_video_paths(folder=folder)
             for info in [VideoFileMetadata.from_path(path=path)]}
    return {"sourceSizes":sizes, "root":str(root), "displayName":root.name, "id":root.name, "parentDirectory":str(root.parent),
            "labelSource":register_label_source(root,root/"skellyclicker"), "issues":[]}


@resources.get("/core/freemocap/recordings/{recording_id}/playback/bundle")
def labeling_bundle(recording_id: str, recording_parent_directory: str):
    """Label the original camera images using Core's timeline, calibration and media URLs."""
    bundle = playback.get_recording_bundle(recording_id, recording_parent_directory)
    source = PlaybackVideoSource.SYNCHRONIZED
    raw = bundle.videos.sources[source]
    if not raw.valid:
        raise HTTPException(422, "The synchronized camera videos have inconsistent frame counts or could not be read.")
    cameras = {camera.id for camera in bundle.calibration.cameras} if bundle.calibration else set()
    media = tuple(item for item in bundle.media if item.video_source == source)
    ids = {item.video_filename:item.timeline.source for item in media}
    views = []
    for video in raw.videos:
        camera = ids[video.filename]
        if camera not in cameras:
            # Older recordings lack explicit camera-to-filename associations.
            stem = Path(video.filename).stem
            matches = [name for name in cameras if stem == name or stem.endswith("_" + name)]
            camera = matches[0] if len(matches) == 1 else video.video_id
        views.append(video.model_copy(update={"video_id":camera}))
    if len({view.video_id for view in views}) != len(views):
        raise HTTPException(422, "Multiple synchronized videos map to one camera.")
    return bundle.model_copy(update={"media":media, "videos":bundle.videos.model_copy(update={
        "preferred_source":source, "sources":{source:raw.model_copy(update={"videos":views})}})})


# Core emits media URLs rooted at /freemocap. Keep the reader's lease, streaming
# cleanup, timing, and range responses intact on both desktop playback paths.
for path, handler in (
    ("/freemocap/recordings/{recording_id}/videos/{video_id}", playback.stream_video),
    ("/freemocap/recordings/{recording_id}/videos/{video_id}/browser", playback.browser_video_stream),
    ("/core/freemocap/recordings/{recording_id}/parquet", playback.get_recording_parquet),
):
    resources.add_api_route(path, handler, methods=["GET"])


class OpenFolder(BaseModel):
    path: str


@router.post("/recordings/open")
def open_folder(request: OpenFolder):
    try:
        return open_recording(Path(request.path))
    except (OSError, ValueError) as error:
        raise HTTPException(422, str(error)) from error


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Observation(StrictModel):
    point: str
    camera_id: str
    source_frame: int = Field(ge=0)
    x_px: float = Field(ge=0)
    y_px: float = Field(ge=0)
    origin: Literal["click", "accepted"]


class LabelSession(StrictModel):
    active_point: str | None
    active_camera: str | None
    source_frame: int | None = Field(ge=0)
    local_frame_index: int | None = Field(ge=0)


class LabelDocument(StrictModel):
    schema_version: Literal[1]
    recording_id: str
    tracked_point_names: list[str]
    observations: list[Observation]
    session: LabelSession

    @model_validator(mode="after")
    def validate_names(self):
        names = set(self.tracked_point_names)
        keys = {(row.point,row.source_frame,row.camera_id) for row in self.observations}
        if len(names) != len(self.tracked_point_names) or any(not n.strip() for n in names):
            raise ValueError("Point names must be distinct and nonempty")
        if len(keys) != len(self.observations) or any(row.point not in names for row in self.observations):
            raise ValueError("Duplicate observation or unknown point")
        if self.session.active_point is not None and self.session.active_point not in names:
            raise ValueError("Unknown active point")
        return self


class SaveLabels(StrictModel):
    recording_id: str
    recording_parent_directory: str
    document: LabelDocument


def labels_path(recording_id, parent):
    directory = _sources.get((recording_id, parent))
    if directory is None:
        raise HTTPException(404, "Open this recording before accessing labels")
    return directory / "manual-labels.json"


@router.get("/labels")
def read_labels(recording_id: str, recording_parent_directory: str):
    path = labels_path(recording_id, recording_parent_directory)
    with _lock:
        return {"document": LabelDocument.model_validate_json(path.read_bytes()) if path.exists() else None}


@router.put("/labels")
def save_labels(request: SaveLabels):
    if request.recording_id != request.document.recording_id:
        raise HTTPException(422, "Label recording identity mismatch")
    path = labels_path(request.recording_id, request.recording_parent_directory)
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(path, request.document.model_dump())
    return {"document": request.document}
