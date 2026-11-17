"""Recording-local DLC runs from manually clicked source frames."""
import json
from pathlib import Path
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from freemocap_sdk.storage import atomic_json, file_digest, resolve_relative
from pydantic import BaseModel, Field

from .job_lifecycle import busy, guard, jobs
from .gpu_runtime import training_python
from .manual_recording import LabelDocument, labels_path
from .manual_training import freeze_clicks
from .training_pipeline import run_worker
from .training_routes import launch_training

router = APIRouter(prefix="/api/keypoint-training")


class RoundRequest(BaseModel):
    recording_id: str
    recording_parent_directory: str
    training_frames: set[int]
    validation_frames: set[int]
    python_path: str = Field(default_factory=training_python)
    epochs: int = Field(default=10, ge=1, le=10000)
    max_seconds: int = Field(default=3600, ge=30, le=86400)
    parent_run_id: UUID | None = None


def read(path):
    return json.loads(path.read_bytes())


def run_directory(recording_id, parent):
    return labels_path(recording_id, parent).parent/"keypoint-training-runs"


@router.get("/runs")
def list_rounds(recording_id: str, recording_parent_directory: str):
    directory = run_directory(recording_id, recording_parent_directory)
    rounds = []
    for path in sorted(directory.glob("*/request.json"), key=lambda p:p.stat().st_mtime, reverse=True):
        work = path.parent
        live = jobs.get(work.name)
        snapshot = live["run"].snapshot() if live else read(work/"status.json") if (work/"status.json").exists() else {}
        status = snapshot.get("status", "failed")
        if not live and status in ("queued", "running"):
            status = "failed"
        error = next((op.get("error") for op in snapshot.get("operations", []) if op.get("error")), None)
        request = read(path)
        rounds.append({"id":work.name, "status":status, "error":error or snapshot.get("error"),
                       "epochs":request["epochs"], "validation_frames":sorted(request["validation_frames"]),
                       "stage":next((op.get("detail") or op.get("label") for op in snapshot.get("operations", [])
                                     if op["status"] == "running"), None)})
    return rounds


@router.get("/runs/{run_id}/artifact")
def artifact(run_id: UUID, recording_id: str, recording_parent_directory: str, path: str):
    try:
        asset = resolve_relative(run_directory(recording_id, recording_parent_directory)/str(run_id), path)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    if not asset.is_file():
        raise HTTPException(404, "Artifact not found")
    return FileResponse(asset)


@router.post("/runs", status_code=202)
def start_round(request: RoundRequest):
    path = labels_path(request.recording_id, request.recording_parent_directory)
    directory = run_directory(request.recording_id, request.recording_parent_directory)
    with guard:
        if busy():
            raise HTTPException(409, "Another processing run is active")
        try:
            if not Path(request.python_path).is_absolute() or not Path(request.python_path).is_file():
                raise ValueError("DeepLabCut is unavailable. Run poe dev to prepare the training environment, or provision the installed app's GPU workers.")
            if not path.exists():
                raise ValueError("Save keypoint clicks before starting a training round")
            doc = LabelDocument.model_validate_json(path.read_bytes())
            clicks = {row.source_frame for row in doc.observations if row.origin == "click"}
            train, validate = request.training_frames, request.validation_frames
            if not train or not validate or train & validate or not (train | validate) <= clicks:
                raise ValueError("Select distinct clicked frames for training and validation")
            parent = None
            if request.parent_run_id:
                previous = directory/str(request.parent_run_id)
                result = read(previous/"result.json")
                frozen = read(previous/"dataset"/"manifest.json")
                if frozen["keypoint_names"] != doc.tracked_point_names:
                    raise ValueError("Parent checkpoint has different keypoint names or order")
                if validate != set(read(previous/"request.json")["validation_frames"]):
                    raise ValueError("Keep the same validation frames when continuing a run")
                parent = resolve_relative(previous, result["checkpoint"])
                if file_digest(parent) != result["checkpoint_sha256"]:
                    raise ValueError("Parent checkpoint changed")
        except (OSError, ValueError, KeyError) as error:
            raise HTTPException(422, str(error)) from error

        def handlers(config, job):
            work = job["work"]
            query = urlencode(dict(recording_id=config.recording_id, recording_parent_directory=config.recording_parent_directory))
            job["artifact_url"] = f"/api/keypoint-training/runs/{work.name}/artifact?{query}"
            def freeze(inputs, ctx):
                recording = Path(config.recording_parent_directory)/config.recording_id
                freeze_clicks(recording, work, train, validate, config.epochs, parent, doc=doc, check_cancelled=ctx.check_cancelled)
                return {"dataset":str(work/"dataset")}
            def prepare(inputs, ctx):
                run_worker("prepare", job, ctx)
                return {"prepared":str(work)}
            def train_model(inputs, ctx):
                run_worker("train", job, ctx)
                return {"trained":str(work)}
            def publish(inputs, ctx):
                trained = read(work/"trained.json")
                checkpoint = resolve_relative(work, trained["checkpoint"])
                if file_digest(checkpoint) != trained["checkpoint_sha256"]:
                    raise ValueError("Completed checkpoint changed")
                atomic_json(work/"result.json", trained)
                ctx.artifacts(writes=(work/"result.json", checkpoint))
                return {"result":trained}
            return dict(freeze_inputs=freeze, prepare_trainer=prepare, train_model=train_model, publish_run=publish)
        return launch_training(request, path, directory, handlers)
