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


def checkpoints(project_path, run_id, *, metric=None):
    folder=folder_for(project_path,run_id);events=folder/'events.jsonl';published={};errors={};poses={};tails={};coverage={}
    if events.is_file():
        for line in events.read_text(encoding='utf-8').splitlines():
            try:event=json.loads(line)
            except json.JSONDecodeError:continue  # A live writer may have an unfinished last line.
            if event.get('kind')=='metric' and event.get('id')=='validation_mean_px' and math.isfinite(event['value']):errors[event['step']]=event['value']
            if event.get('kind')=='metric' and event.get('id')=='validation_p95_px' and math.isfinite(event['value']):tails[event['step']]=event['value']
            if event.get('kind')=='keypoint_validation':coverage[event['epoch']]=event
            if event.get('kind')=='pose_validation':poses[event['epoch']]=event
            if event.get('kind')=='checkpoint' and re.fullmatch(r'checkpoints/epoch-\d{6}\.pt',event.get('path','')):
                path=resolve_relative(folder,event['path'])
                if path.is_file():published[event['epoch']]={'path':event['path'],'sha256':event['sha256'],'epoch':event['epoch'],'bytes':path.stat().st_size}
    values=[{**v,'validation_mean_px':errors.get(epoch),'pose_validation':poses.get(epoch),'validation_p95_px':tails.get(epoch),'keypoint_validation':coverage.get(epoch)} for epoch,v in sorted(published.items())]
    saved=json.loads((folder/'request.json').read_text(encoding='utf-8')) if (folder/'request.json').exists() else {}
    policy=metric or saved.get('checkpoint_metric','pose')
    best,reason=recommend(values,policy=policy)
    return {'checkpoints':values,'recommended_path':best['path'] if best else None,'recommendation':reason}


def recommend(values,policy='pose'):
    if policy in ('mean_px','p95_px'):
        key='validation_mean_px' if policy=='mean_px' else 'validation_p95_px'
        # Never reward dropped predictions with a smaller finite-only mean.
        complete=[v for v in values if v.get(key) is not None and (v.get('keypoint_validation') is None or v['keypoint_validation']['missing_points']==0)]
        if not complete:return None,'No checkpoint has a complete finite prediction set for the selected 2D metric; missing predictions are not zero error.'
        best=min(complete,key=lambda v:(v[key],-v['epoch']))
        coverage=best.get('keypoint_validation')
        note=(f"Coverage {coverage['predicted_points']}/{coverage['expected_points']} labeled points." if coverage else 'Legacy run: finite-only metric; missing-prediction coverage was not recorded.')
        return best,(f"Epoch {best['epoch']}: lowest {'mean' if policy=='mean_px' else '95th percentile'} raw 2D keypoint error ({best[key]:.3f} px). "
                     'Complete-coverage checkpoints only when coverage is recorded; latest epoch breaks ties. Pose estimates and training loss do not rank this selection. '+note)

    measured=[v for v in values if v['validation_mean_px'] is not None]
    pose=[v for v in measured if v.get('pose_validation') and v['pose_validation']['reference_images']>0
          and all(math.isfinite(v['pose_validation']['metrics'].get(k,float('nan'))) for k in
                  ('validation_position_mm','validation_orientation_deg','validation_pose_failure_pct'))]
    # Compare only equal reference coverage within this immutable dataset.
    if pose and len({v['pose_validation']['reference_images'] for v in pose})==1:
        failure=min(v['pose_validation']['metrics']['validation_pose_failure_pct'] for v in pose)
        candidates=[v for v in pose if v['pose_validation']['metrics']['validation_pose_failure_pct']==failure]
        def measures(v):
            m=v['pose_validation']['metrics']
            return (m['validation_position_mm'],m['validation_orientation_deg'],v['validation_mean_px'])
        def rank(v):return sum(sum(measures(other)[axis]<value for other in candidates) for axis,value in enumerate(measures(v)))
        best=min(candidates,key=lambda v:(rank(v),v['validation_mean_px'],-v['epoch']))
        position,orientation,pixel=measures(best);coverage=best['pose_validation']
        reason=(f"Epoch {best['epoch']}: {failure:.1f}% pose failures, {position:.2f} mm mean position error, "
                f"{orientation:.2f} deg mean orientation error, {pixel:.2f} px mean keypoint error. "
                "Policy v1: lowest pose failure rate first; then lowest sum of equally weighted position, orientation and keypoint error ranks. "
                "Ties use keypoint error, then latest epoch. "
                f"Pose reference coverage: {coverage['reference_images']}/{coverage['validation_images']} images; errors describe successful estimates. "
                "Agreement with stereo/pose labels, not independent ground truth. "
                f"Compared {len(pose)} pose-evaluated checkpoints; {len(values)-len(pose)} without complete pose metrics excluded.")
        return best,reason
    best=min(measured,key=lambda v:(v['validation_mean_px'],-v['epoch'])) if measured else (values[-1] if values else None)
    if not best:return None,'No published checkpoints are available.'
    reason=(f"Epoch {best['epoch']}: lowest measured mean validation keypoint error ({best['validation_mean_px']:.2f} px); ties choose the latest epoch. "
            if measured else f"Epoch {best['epoch']}: latest saved checkpoint; no validation metrics available. ")
    return best,reason+'Pose-based comparison is unavailable: no comparable successful pose evaluations. Older runs are not retroactively evaluated; new rounds include pose validation. Training loss does not select the checkpoint.'



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
