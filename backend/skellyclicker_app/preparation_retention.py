"""Preserve existing labeled reference geometry when expanding preparation coverage."""
import json
import shutil
from uuid import uuid4
import pyarrow.parquet as pq
from freemocap_sdk.storage import atomic_json, file_digest, publish_directory, resolve_relative
from .projects import Project, read_model, recording_structure
from .label_inputs import checked


def retain_labeled_frames(job, rows, calibration):
    from .label_routes import result_view
    project=read_model(job['manifest'],Project)
    previous=result_view(job['manifest'])
    if not previous:return rows, None
    metadata=previous['manifest'];root=job['root'];output=job['output']
    old=resolve_relative(root,metadata['pose_result'])
    if file_digest(old/'manifest.json')!=metadata['pose_manifest_sha256']:raise ValueError('Existing reference manifest changed')
    authority=json.loads((old/'manifest.json').read_text())
    if len(project.target_manifests)!=1 or file_digest(resolve_relative(job['root'],project.target_manifests[0]))!=metadata['target_manifest_sha256']:
        raise ValueError('Existing label target definition changed; existing dataset was preserved')
    if (metadata['source_sha256']!=job['request']['source_sha256'] or metadata['stl_sha256']!=job['request']['target_sha256']
        or metadata['stl_units']!=job['request']['stl_units'] or file_digest(output/'calibration.json')!=metadata['calibration_sha256']):
        raise ValueError('Existing labels use different source, target, units or calibration. Existing dataset was preserved.')
    retained={int(m['source_frame']) for m in previous['moments']}
    if not retained<={r['source_frame'] for r in rows}:
        raise ValueError('The new preparation must cover existing labeled frames. Choose Entire recording to preserve them.')
    old_rows={r['source_frame']:r for r in pq.read_table(checked(old/'candidates.parquet',authority['files']['candidates.parquet'])).to_pylist()}
    old_timing={r['source_frame']:r['timestamp_ns'] for r in pq.read_table(checked(old/'timing.parquet',authority['files']['timing.parquet'])).to_pylist()}
    for row in rows:
        frame=row['source_frame']
        if frame not in retained:continue
        if old_timing[frame]!=row['timestamp_ns']:raise ValueError('Retained source timestamps changed')
        # Keep complete reference rows, images, depth and clouds from one source.
        row.clear();row.update(old_rows[frame])
        for name,identity in authority['files'].items():
            if name.startswith(f'frames/{frame:06d}-') or name==f'point_cloud/{frame:06d}.npz':
                source=checked(old/name,identity);destination=output/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
    cloud=output/'point_cloud/manifest.json'
    if cloud.exists():
        current=json.loads(cloud.read_text());prior=json.loads(checked(old/'point_cloud/manifest.json',authority['files']['point_cloud/manifest.json']).read_text())
        old_cloud={r['source_frame']:r for r in prior['frames']}
        current['frames']=[old_cloud[r['source_frame']] if r['source_frame'] in retained else r for r in current['frames']]
        atomic_json(cloud,current)
    provenance={'pose_result':metadata['pose_result'],'pose_manifest_sha256':metadata['pose_manifest_sha256'],'label_result':previous['path'],
                'label_manifest_sha256':previous['manifest_sha256'],'source_frames':sorted(retained),'policy':'Preserve complete reference rows for every existing labeled image, including excluded images; other frames use this preparation run.'}
    return rows, provenance


def rebase_labels(root, project, prepared, retention):
    """Stage immutable pointer revisions; caller atomically activates the complete project."""
    if retention is None:return
    old_folder=resolve_relative(root,project.label_result);old_meta=json.loads((old_folder/'manifest.json').read_text())
    if file_digest(old_folder/'manifest.json')!=retention['label_manifest_sha256']:raise ValueError('Labels changed during preparation')
    revision='reference-'+uuid4().hex[:12];extension=recording_structure(root,old_meta['recording_id']).application_dir('skellyclicker')
    staged=extension/'working/labels'/revision;staged.mkdir(parents=True)
    for name,identity in old_meta['files'].items():
        source=checked(old_folder/name,identity);destination=staged/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
    metadata={**old_meta,'pose_result':prepared,'pose_manifest_sha256':file_digest(resolve_relative(root,prepared)/'manifest.json'),
              'previous_label_result':project.label_result,'previous_label_manifest_sha256':retention['label_manifest_sha256'],
              'reference_rebase':retention}
    atomic_json(staged/'manifest.json',metadata)
    destination=extension/'labels'/revision/'r001';destination.parent.mkdir(parents=True,exist_ok=True);publish_directory(staging=staged,destination=destination)
    project.label_result=destination.relative_to(root).as_posix()
    if project.active_review:
        old_review=resolve_relative(root,project.active_review);review=json.loads((old_review/'manifest.json').read_text());staged=extension/'working/reviews'/revision;staged.mkdir(parents=True)
        for name,identity in review['files'].items():shutil.copyfile(checked(old_review/name,identity),staged/name)
        atomic_json(staged/'manifest.json',{**review,'label_result':project.label_result,'label_manifest_sha256':file_digest(destination/'manifest.json'),
                    'previous_selection_sha256':file_digest(old_review/'manifest.json'),'reference_rebase':retention})
        destination=extension/'reviews'/revision;destination.parent.mkdir(parents=True,exist_ok=True);publish_directory(staging=staged,destination=destination)
        project.active_review=destination.relative_to(root).as_posix()
