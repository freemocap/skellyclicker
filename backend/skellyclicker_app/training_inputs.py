"""Immutable, approved training inputs; APP owns split policy and label semantics."""
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import Field
from freemocap_sdk.storage import atomic_json, file_digest, inventory, project_lock, publish_directory, resolve_relative
from .projects import Model, Project, read_model, load_target, recording_structure
from .label_inputs import checked, StaleInputs
from .authored_geometry import load_authored_geometry


class TrainingInputs(Model):
    project_path: str
    validation_fraction: float = Field(default=.2, gt=0, lt=.5)
    guard_seconds: float = Field(default=1, ge=0, le=60)
    expected_selection_sha256: str | None = Field(default=None, pattern='^[a-f0-9]{64}$')
    expected_label_manifest_sha256: str | None = Field(default=None, pattern='^[a-f0-9]{64}$')


def bind_training_inputs(request):
    # Import here to keep selection endpoints independent of training execution.
    from .label_routes import result_view, selection_view
    path=Path(request.project_path).resolve();root=path.parent
    project=read_model(path,Project);result=result_view(path);selection=selection_view(path)
    if not result or not project.active_review or not selection['selected_image_ids']:
        raise ValueError('Include images before starting training')
    if request.expected_selection_sha256 and request.expected_selection_sha256!=selection['sha256']:
        raise StaleInputs('Included images changed; refresh the training configuration')
    if request.expected_label_manifest_sha256 and request.expected_label_manifest_sha256!=result['manifest_sha256']:
        raise StaleInputs('Generated labels changed; refresh the training configuration')
    review_dir=resolve_relative(root,project.active_review)
    review=json.loads((review_dir/'manifest.json').read_text())
    metadata=result['manifest']
    if review['label_manifest_sha256']!=result['manifest_sha256'] or review['label_result']!=result['path']:
        raise StaleInputs('Selection belongs to another label result')
    if project.sample_result!=metadata['pose_result'] or len(project.target_manifests)!=1:
        raise StaleInputs('Selected poses or target changed')
    target_path=resolve_relative(root,project.target_manifests[0]);target=load_target(root,project.target_manifests[0])
    if file_digest(target_path)!=metadata['target_manifest_sha256']:
        raise StaleInputs('Selected target changed')
    checked(resolve_relative(root,target.geometry.path),target.geometry.model_dump())
    authored=load_authored_geometry(root,target)
    if not authored or list(authored['names'])!=metadata['keypoint_names'] or authored['manifest']['keypoints']['sha256']!=metadata['keypoint_definition_sha256']:
        raise StaleInputs('Authored keypoint definition changed')
    pose=resolve_relative(root,project.sample_result)
    if file_digest(pose/'manifest.json')!=metadata['pose_manifest_sha256'] or file_digest(pose/'calibration.json')!=metadata['calibration_sha256']:
        raise StaleInputs('Pose or calibration artifact changed')
    ids=set(selection['selected_image_ids']);images=[r for r in result['images'] if r['image_id'] in ids]
    if len(images)!=len(ids):raise ValueError('Unknown or duplicate selected image identity')
    moments=sorted({r['moment_id']:(int(r['timestamp_ns']),r['source_frame']) for r in images}.items(),key=lambda v:v[1])
    if len(moments)<3:raise ValueError('At least three distinct moments are needed for a temporal training/validation split')
    validation_count=max(1,math.ceil(len(moments)*request.validation_fraction))
    boundary=moments[-validation_count][1][0];guard_ns=round(request.guard_seconds*1_000_000_000)
    roles={mid:('validation' if stamp>=boundary else 'guard' if boundary-stamp<=guard_ns else 'training') for mid,(stamp,frame) in moments}
    images=[{**r,'timestamp_ns':int(r['timestamp_ns']),'split':roles[r['moment_id']]} for r in images]
    counts={role:sum(r['split']==role for r in images) for role in ('training','validation','guard')}

    labels=pq.read_table(resolve_relative(root,result['path'])/'labels.parquet').to_pylist()
    labels=[r for r in labels if r['moment_id']+':'+r['camera_id'] in ids]
    by_image={i:[] for i in ids}
    for row in labels:by_image[row['moment_id']+':'+row['camera_id']].append(row['keypoint_index'])
    expected=list(range(len(authored['names'])))
    if any(sorted(indices)!=expected for indices in by_image.values()):raise ValueError('Incomplete or duplicate ordered keypoint labels')
    for row in images:checked(resolve_relative(root,row['path']),row)
    from .training_checkpoints import bind_parent
    parent=bind_parent(request,{'project_uuid':project.uuid,'stl_sha256':target.geometry.sha256,'stl_units':target.authored_units,'keypoint_names':list(authored['names']),'keypoint_definition_source_sha256':metadata['keypoint_definition_sha256']})
    if parent:
        # Keep the parent's temporal boundary fixed: new examples must not move
        # its evaluation images into optimization. Earlier rounds stay immutable.
        previous=parent['dataset']['manifest']
        if previous['source_sha256']!=metadata['source_sha256']:raise ValueError('Continued training currently requires the same recording')
        boundary=int(previous['validation_start_ns']);guard_ns=round(previous['guard_seconds']*1_000_000_000)
        roles={mid:('validation' if stamp>=boundary else 'guard' if boundary-stamp<=guard_ns else 'training') for mid,(stamp,frame) in moments}
        images=[{**r,'split':roles[r['moment_id']]} for r in images]
        counts={role:sum(r['split']==role for r in images) for role in ('training','validation','guard')}
        if not counts['training'] or not counts['validation']:raise ValueError('Keep training and validation examples when continuing a model')
    if not counts['training']:raise ValueError('Guard interval leaves no training images; reduce it or include more separated moments')
    return dict(guard_seconds=guard_ns/1_000_000_000,validation_fraction=parent['dataset']['manifest']['validation_fraction'] if parent else request.validation_fraction,parent=parent,root=root,path=path,project=project,result=result,selection=selection,review=review,images=images,labels=labels,
                target=target,authored=authored,pose=pose,counts=counts,validation_start_ns=boundary)


def training_input_preview(request):
    bound=bind_training_inputs(request)
    return {'expected_selection_sha256':bound['selection']['sha256'],'expected_label_manifest_sha256':bound['result']['manifest_sha256'],
            'parent_checkpoint':({k:v for k,v in bound['parent'].items() if k not in ('dataset','source_path')} if bound['parent'] else None),'image_count':len(bound['images']),'moment_count':len({r['moment_id'] for r in bound['images']}),
            'keypoint_count':len(bound['authored']['names']),'counts':bound['counts'],
            'validation_start_ns':str(bound['validation_start_ns']),'guard_seconds':bound['guard_seconds'],
            'split_policy':'temporal_tail_with_guard','review_state':'approved',
            'images':[{k:(str(r[k]) if k=='timestamp_ns' else r[k]) for k in ('image_id','moment_id','camera_id','source_frame','timestamp_ns','split')} for r in bound['images']]}


def freeze_training_inputs(request, *, check_cancelled=lambda:None):
    path=Path(request.project_path).resolve()
    with project_lock(path.parent):
        bound=bind_training_inputs(request);root=bound['root'];project=bound['project'];result=bound['result']
        extension=recording_structure(root,result['manifest']['recording_id']).application_dir('skellyclicker')
        revision='dataset-'+uuid4().hex[:12];staged=extension/'working'/'training-inputs'/revision
        staged.mkdir(parents=True);(staged/'images').mkdir()
        rows=[]
        for row in bound['images']:
            check_cancelled();source=resolve_relative(root,row['path'])
            relative=f"images/{row['source_frame']:09d}-{row['camera_id']}.png"
            shutil.copyfile(source,staged/relative);checked(staged/relative,row)
            rows.append({**row,'source_path':row['path'],'path':relative,'review_state':'approved'})
        pq.write_table(pa.Table.from_pylist(rows),staged/'images.parquet')
        pq.write_table(pa.Table.from_pylist(bound['labels']),staged/'labels.parquet')
        shutil.copyfile(bound['pose']/'calibration.json',staged/'calibration.json')
        shutil.copyfile(resolve_relative(root,bound['target'].geometry.path),staged/'target.stl')
        atomic_json(staged/'keypoints.json',bound['authored']['definition'])
        shutil.copyfile(resolve_relative(root,project.active_review)/'manifest.json',staged/'selection-manifest.json')
        shutil.copyfile(resolve_relative(root,project.active_review)/'selection.parquet',staged/'selection.parquet')
        shutil.copyfile(resolve_relative(root,result['path'])/'manifest.json',staged/'label-manifest.json')
        check_cancelled()
        # Every approved image is retained, including guard-band images excluded from optimization/evaluation.
        metadata={'schema_version':1,'dataset_id':revision,'created_at':datetime.now(timezone.utc).isoformat(),
                  'parent_checkpoint':({k:v for k,v in bound['parent'].items() if k not in ('dataset','source_path')} if bound['parent'] else None),'project_uuid':project.uuid,'recording_id':result['manifest']['recording_id'],
                  'selection_path':project.active_review,'selection_sha256':bound['selection']['sha256'],
                  'label_result':result['path'],'label_manifest_sha256':result['manifest_sha256'],
                  'review_state':'approved','approval_basis':'included_selection_at_training_start',
                  'source_selection_initialization':bound['review'].get('initialization'),
                  'label_origin':result['manifest']['label_origin'],'keypoint_names':list(bound['authored']['names']),
                  'stl_sha256':bound['target'].geometry.sha256,'stl_units':bound['target'].authored_units,
                  'calibration_sha256':result['manifest']['calibration_sha256'],
                  'keypoint_definition_source_sha256':result['manifest']['keypoint_definition_sha256'],
                  'source_sha256':result['manifest']['source_sha256'],
                  'pixel_convention':'opencv_integer_pixel_centres','timestamp_unit':'ns',
                  'image_count':len(rows),'counts':bound['counts'],'split_policy':'temporal_tail_with_guard',
                  'validation_fraction':bound['validation_fraction'],'guard_seconds':bound['guard_seconds'],
                  'validation_start_ns':str(bound['validation_start_ns']),
                  'files':{k:v.model_dump() for k,v in inventory(staged).items()}}
        for name,identity in metadata['files'].items():checked(staged/name,identity)
        if file_digest(staged/'target.stl')!=metadata['stl_sha256'] or file_digest(staged/'calibration.json')!=metadata['calibration_sha256']:
            raise StaleInputs('Inputs changed while copying the snapshot')
        atomic_json(staged/'manifest.json',metadata);check_cancelled()
        destination=extension/'training-inputs'/revision;destination.parent.mkdir(parents=True,exist_ok=True)
        publish_directory(staging=staged,destination=destination)
        return {'path':destination.relative_to(root).as_posix(),'manifest_sha256':file_digest(destination/'manifest.json'),'manifest':metadata}
