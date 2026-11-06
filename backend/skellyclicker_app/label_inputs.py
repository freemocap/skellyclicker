"""App-owned prepared-data bindings and deterministic label configuration."""
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal
import pyarrow.parquet as pq
from pydantic import Field, model_validator
from freemocap_sdk.storage import file_digest, resolve_relative
from .projects import Model, Project, Recording, read_model, load_target
from .authored_geometry import load_authored_geometry


class PreviewLabels(Model):
    project_path: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0)
    step: int = Field(default=1, ge=1)
    max_moments: int | None = Field(default=None, ge=1)
    image_keys: list[str] | None = None
    fit_filter: Literal['all','passed','failed'] = 'all'

    @model_validator(mode='after')
    def ordered(self):
        if self.end_frame < self.start_frame: raise ValueError('End frame precedes start frame')
        if self.image_keys is not None:
            import re
            if not self.image_keys or len(set(self.image_keys))!=len(self.image_keys) or any(not re.fullmatch(r'[0-9]+:(left|right)',key) for key in self.image_keys):raise ValueError('Choose distinct source-frame and camera identities')
            if any(not self.start_frame<=int(key.split(':')[0])<=self.end_frame for key in self.image_keys):raise ValueError('Selected images lie outside the requested range')
        return self


class GenerateLabels(PreviewLabels):
    expected_pose_manifest_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    expected_target_manifest_sha256: str = Field(pattern='^[a-f0-9]{64}$')


class StaleInputs(ValueError):
    pass


def checked(path, identity):
    if not path.is_file() or path.stat().st_size != identity['bytes'] or file_digest(path) != identity['sha256']:
        raise ValueError(f'Missing or changed artifact: {path}')
    return path


@dataclass
class BoundInputs:
    manifest: Path
    project: Project
    recording: Recording
    target: object
    authored: dict
    result: Path
    authority: dict
    rows: list
    selected: list
    pose_hash: str
    target_hash: str
    target_path: Path

    @property
    def root(self): return self.manifest.parent


def bind_inputs(request: PreviewLabels, *, verify_source=False) -> BoundInputs:
    manifest=Path(request.project_path).expanduser().resolve()
    if manifest.is_dir():
        matches=list(manifest.glob('*_project.json'))
        if len(matches)!=1: raise ValueError('Select an unambiguous project manifest')
        manifest=matches[0]
    project=read_model(manifest,Project)
    if len(project.recording_manifests)!=1 or len(project.target_manifests)!=1 or not project.sample_result:
        raise ValueError('Prepared labeling requires one recording, one target and a prepared result')
    recording=read_model(resolve_relative(manifest.parent,project.recording_manifests[0]),Recording)
    target_path=resolve_relative(manifest.parent,project.target_manifests[0])
    target=load_target(manifest.parent,project.target_manifests[0])
    result=resolve_relative(manifest.parent,project.sample_result)
    pose_hash=file_digest(result/'manifest.json');target_hash=file_digest(target_path)
    if isinstance(request,GenerateLabels) and (request.expected_pose_manifest_sha256!=pose_hash or request.expected_target_manifest_sha256!=target_hash):
        raise StaleInputs('Inputs changed since preview; preview the current inputs again')
    authority=json.loads((result/'manifest.json').read_text(encoding='utf-8'))
    descriptor=authority['descriptor']
    if descriptor['recording_id']!=recording.recording_id or descriptor['source_sha256']!=recording.source.sha256 or descriptor['target_sha256']!=target.geometry.sha256 or descriptor['geometry']['source_units']!=target.authored_units:
        raise StaleInputs('Prepared poses do not match the recording, target geometry or units')
    checked(resolve_relative(manifest.parent,target.geometry.path),target.geometry.model_dump())
    if verify_source: checked(Path(recording.source.path),recording.source.model_dump())
    for name in ['candidates.parquet','timing.parquet','calibration.json']:
        checked(result/name,authority['files'][name])
    authored=load_authored_geometry(manifest.parent,target)
    if authored is None: raise ValueError('This target has no ordered authored keypoint definition')
    rows=pq.read_table(result/'candidates.parquet').to_pylist()
    timing=pq.read_table(result/'timing.parquet').to_pylist()
    ids=[r['source_frame'] for r in rows]
    if ids!=sorted(set(ids)) or [(r['source_frame'],r['timestamp_ns']) for r in rows]!=[(r['source_frame'],r['timestamp_ns']) for r in timing]:
        raise ValueError('Candidate and timing source identities disagree')
    if any(b['timestamp_ns']<=a['timestamp_ns'] for a,b in zip(rows,rows[1:])):
        raise ValueError('Source timestamps must increase strictly')
    requested={int(key.split(':')[0]) for key in request.image_keys} if request.image_keys else set(range(request.start_frame,request.end_frame+1))
    if not requested.issubset(ids):
        raise ValueError('Prepared data does not cover every requested source frame')
    selected=[r for r in rows if request.start_frame<=r['source_frame']<=request.end_frame and (request.fit_filter=='all' or bool(r['accepted'])==(request.fit_filter=='passed'))][::request.step]
    if request.image_keys is not None:selected=[r for r in rows if r['source_frame'] in requested]
    if request.max_moments is not None: selected=selected[:request.max_moments]
    if not selected: raise ValueError('No paired moments match this configuration')
    return BoundInputs(manifest,project,recording,target,authored,result,authority,rows,selected,pose_hash,target_hash,target_path)


def preview(request: PreviewLabels) -> dict:
    bound=bind_inputs(request)
    image_count=len(request.image_keys) if request.image_keys is not None else len(bound.selected)*2
    return {'expected_pose_manifest_sha256':bound.pose_hash,'expected_target_manifest_sha256':bound.target_hash,
            'moment_count':len(bound.selected),'image_count':image_count,
            'label_count':image_count*len(bound.authored['names']),
            'source_frames':[r['source_frame'] for r in bound.selected],
            'timestamps_ns':[str(r['timestamp_ns']) for r in bound.selected],
            'keypoint_names':list(bound.authored['names']), 'review_state':'unreviewed'}
