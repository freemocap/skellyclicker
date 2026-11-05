"""Publish source-specific stereo inputs through the shared SDK recording contract."""
import json
from pathlib import Path
import shutil
import subprocess
import threading
from uuid import uuid4
import numpy as np
from freemocap_sdk.recording_structure import RecordingStructure
from freemocap_sdk.recording_inputs import write_recording_inputs
from freemocap_sdk.storage import atomic_json,file_digest,inventory,project_lock,resolve_relative
from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion
from .projects import Project,Recording,read_model,recording_structure
from .playback_adapter import calibrated_cameras,camera_to_world


def verify_recording_inputs(paths):
    info=json.loads(paths.recording_info_path.read_text(encoding='utf-8'))
    manifest=resolve_relative(paths.full_path,info['input_provenance']['inventory'])
    for relative,identity in json.loads(manifest.read_text(encoding='utf-8'))['files'].items():
        path=resolve_relative(paths.full_path,relative)
        if path.stat().st_size!=identity['bytes'] or file_digest(path)!=identity['sha256']:
            raise ValueError(f'Changed recording input: {path}')
    return info


def ensure_recording_inputs(root:Path,recording:Recording,*,cancel=None):
    from .preparation import runtime_config,run_worker
    cancel=cancel or threading.Event();paths=recording_structure(root,recording.recording_id)
    if paths.recording_info_path.exists():
        info=verify_recording_inputs(paths)
        if info['input_provenance']['source_sha256']!=recording.source.sha256:raise ValueError('Recording source identity mismatch')
        return info
    if file_digest(Path(recording.source.path))!=recording.source.sha256:raise ValueError('Changed source SVO')
    if file_digest(Path(recording.calibration_source.path))!=recording.calibration_source.sha256:raise ValueError('Changed stereo factory config')
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:raise RuntimeError('ffmpeg is required for synchronized stereo views')
    attempt='inputs-'+uuid4().hex[:12]
    extension=paths.application_dir('skellyclicker');work=extension/'working'/attempt
    staged=RecordingStructure(base_directory=work,recording_name=recording.recording_id)
    output=staged.application_dir('skellyclicker')/'inputs'/attempt
    output.mkdir(parents=True)
    config=runtime_config()
    filenames={name:name+'.mp4' for name in ('left','right')}
    request={'source_svo':recording.source.path,'source_sha256':recording.source.sha256,
             'output':str(output),'videos':{name:str(staged.videos_synchronized_dir/filename) for name,filename in filenames.items()},
             'ffmpeg':ffmpeg,'runtime':config}
    atomic_json(work/'request.json',request)
    job={'work':work,'output':output,'request':request,'cancel':cancel,
         'status':{'job_id':attempt,'state':'running','stage':'decode stereo','completed':0,'total':0}}
    run_worker(job,'stereo_decode',config['zed_python'])
    if cancel.is_set():raise InterruptedError('Input publication cancelled')
    samples=json.loads((output/'samples.json').read_text(encoding='utf-8'))
    cal=json.loads((output/'calibration.json').read_text(encoding='utf-8'))
    if len(samples)!=cal['source_frame_count'] or [row['source_frame'] for row in samples]!=list(range(len(samples))):
        raise ValueError('Full-source stereo publication requires all source frames')
    for filename in filenames.values():
        data=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries',
             'stream=nb_frames,width,height','-of','json',str(staged.videos_synchronized_dir/filename)]))['streams'][0]
        if int(data['nb_frames'])!=len(samples) or data['width']!=cal['image_width'] or data['height']!=cal['image_height']:
            raise ValueError('Encoded input coverage differs from the source')
    cameras=calibrated_cameras(cal,camera_to_world())
    rotations={camera['id']:RotationQuaternion.from_array(array=np.array(camera['extrinsics']['quaternion_wxyz'])).to_rotation_vector().tolist() for camera in cameras}
    inventory_relative=staged.relative(output/'input_inventory.json')
    provenance={'source_kind':'linked ZED SVO','source_sha256':recording.source.sha256,
        'calibration_source_sha256':recording.calibration_source.sha256,'rectified':True,
        'calibration_method':'ZED replay calibration; no ChArUco solve claimed',
        'source_frame_count':len(samples),'scope':'full source','input_revision':staged.relative(output),
        'stereo_source_manifest':paths.relative(paths.stereo_manifest_path),'inventory':inventory_relative,
        'coordinate_basis':'blender_x_right_y_forward_z_up','units':'mm','encoding':'H264 CRF18 decoded rectified views'}
    write_recording_inputs(structure=staged,videos=filenames,cameras=cameras,rotation_vectors=rotations,
        timestamps_ns=[row['timestamp_ns'] for row in samples],source_frame_indices=[row['source_frame'] for row in samples],
        source_clock_origin_ns=samples[0]['timestamp_ns'],provenance=provenance,recording_uuid=recording.uuid)
    updated=recording.model_copy(update={'calibration_state':'ready','input_revision':staged.relative(output)})
    staged.stereo_manifest_path.parent.mkdir(parents=True,exist_ok=True)
    atomic_json(staged.stereo_manifest_path,updated.model_dump(mode='json'))
    identities=inventory(staged.full_path)
    atomic_json(output/'input_inventory.json',{'schema_version':1,'files':{key:value.model_dump() for key,value in identities.items() if key!=staged.relative(staged.stereo_manifest_path)}})
    # Publish immutable files first; the shared recording-info file is the final
    # visibility marker. Current project selections are changed separately last.
    entries=list(staged.full_path.rglob('*'));entries.sort(key=lambda path:path==staged.recording_info_path)
    with project_lock(root):
        for source in entries:
            if not source.is_file():continue
            destination=resolve_relative(paths.full_path,staged.relative(source))
            if destination.exists():
                if source==staged.stereo_manifest_path:continue # Source identity exists; update state after successful publication.
                if file_digest(source)!=file_digest(destination):raise FileExistsError(destination)
        for source in entries:
            if not source.is_file():continue
            destination=resolve_relative(paths.full_path,staged.relative(source))
            if destination.exists():continue
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,destination)
            if file_digest(source)!=file_digest(destination):raise ValueError(f'Published input changed: {destination}')
        atomic_json(paths.stereo_manifest_path,updated.model_dump(mode='json'))
    return verify_recording_inputs(paths)
