"""Published checkpoint discovery and verified parent-run bindings."""
import json
import math
import re
from pathlib import Path
from uuid import UUID
from freemocap_sdk.storage import file_digest, resolve_relative
from .projects import Project, Recording, read_model, recording_structure


def folder_for(project_path, run_id):
    UUID(run_id)
    manifest=Path(project_path).resolve();project=read_model(manifest,Project)
    if len(project.recording_manifests)!=1:raise ValueError('Training currently requires one recording')
    recording=read_model(resolve_relative(manifest.parent,project.recording_manifests[0]),Recording)
    folder=recording_structure(manifest.parent,recording.recording_id).application_dir('skellyclicker')/'training-runs'/run_id
    if not folder.is_dir():raise ValueError('Saved training run is unavailable')
    return folder


def checkpoints(project_path, run_id):
    folder=folder_for(project_path,run_id);events=folder/'events.jsonl';published={};errors={}
    if events.is_file():
        for line in events.read_text(encoding='utf-8').splitlines():
            try:event=json.loads(line)
            except json.JSONDecodeError:continue  # A live writer may have an unfinished last line.
            if event.get('kind')=='metric' and event.get('id')=='validation_mean_px' and math.isfinite(event['value']):errors[event['step']]=event['value']
            if event.get('kind')=='checkpoint' and re.fullmatch(r'checkpoints/epoch-\d{6}\.pt',event.get('path','')):
                path=resolve_relative(folder,event['path'])
                if path.is_file():published[event['epoch']]={'path':event['path'],'sha256':event['sha256'],'epoch':event['epoch'],'bytes':path.stat().st_size}
    values=[{**v,'validation_mean_px':errors.get(epoch)} for epoch,v in sorted(published.items())]
    measured=[v for v in values if v['validation_mean_px'] is not None]
    best=min(measured,key=lambda v:(v['validation_mean_px'],-v['epoch'])) if measured else (values[-1] if values else None)
    return {'checkpoints':values,'recommended_path':best['path'] if best else None,'recommendation':'Lowest measured validation keypoint error' if measured else 'Latest saved checkpoint; no validation metric available'}


def bind_parent(request, current_dataset):
    run_id=getattr(request,'parent_run_id',None)
    if not run_id:return None
    folder=folder_for(request.project_path,run_id)
    choice=next((v for v in checkpoints(request.project_path,run_id)['checkpoints'] if v['path']==request.parent_checkpoint),None)
    if not choice or choice['sha256']!=request.parent_checkpoint_sha256:raise ValueError('Checkpoint selection changed or is unavailable; select a saved checkpoint again')
    path=resolve_relative(folder,choice['path'])
    if file_digest(path)!=choice['sha256']:raise ValueError('Saved checkpoint bytes changed; choose an intact checkpoint')
    previous=json.loads((folder/'dataset.json').read_text(encoding='utf-8'))['manifest']
    for key in ('project_uuid','stl_sha256','stl_units','keypoint_names','keypoint_definition_source_sha256'):
        if previous[key]!=current_dataset[key]:raise ValueError('Checkpoint target or keypoint definition differs from the current dataset: '+key)
    return {**choice,'run_id':run_id,'source_path':str(path),'dataset':json.loads((folder/'dataset.json').read_text(encoding='utf-8')),'initialization':'model_weights_with_fresh_optimizer'}
