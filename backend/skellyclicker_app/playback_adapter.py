"""Convert app-owned fresh candidates into the SDK's existing recorded playback contract."""
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse
import itertools
import json
import logging
import re
import shutil
import subprocess
from uuid import uuid4
import numpy as np
import pyarrow.parquet as pq
import trimesh
from PIL import Image, ImageDraw
from freemocap_sdk.storage import atomic_json, file_digest, inventory, project_lock, publish_directory, resolve_relative
from freemocap_sdk.recording import (RecordingTimeline, RecordingChannel, ChannelSamples, PlaybackRun,
    PlaybackMedia, PlaybackManifest, RecordingResources, write_playback, create_recording_router)
from skellyforge.core.skeleton.stl_rigid_body import build_stl_rigid_body
from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion
from skellyforge.core.math.geometry.coordinate_systems import (
    AnatomicalDirection, CoordinateSystemConvention, CoordinateSystemRegistry, CoordinateSystemTransform)
from .projects import Project, Target, read_model, recording_structure, load_target
from .authored_geometry import load_authored_geometry, project_authored_geometry, camera_projections

logger=logging.getLogger('skellyclicker.playback')
_registered: dict[str, RecordingResources]={}
_clouds: dict[str, Path]={}

def resolve_recording(recording_id):
    return _registered[recording_id]

router=create_recording_router(resolve_recording)


@router.get('/{recording_id}/point-cloud/{filename}')
def point_cloud_file(recording_id: str, filename: str):
    folder=_clouds.get(recording_id)
    if folder is None:raise HTTPException(404,'No published point cloud')
    if filename!='manifest.json' and not re.fullmatch(r'chunk-\d{4}\.bin',filename):
        raise HTTPException(404,'Unknown cloud resource')
    path=resolve_relative(folder,filename)
    if not path.is_file():raise HTTPException(404,'Missing cloud resource')
    return FileResponse(path,media_type='application/json' if filename.endswith('.json') else 'application/octet-stream',
        headers={'Cache-Control':'public, max-age=31536000, immutable'})


def register_project(root: Path, project: Project):
    if not project.playback_result: return None
    folder=resolve_relative(root,project.playback_result)
    manifest=PlaybackManifest.model_validate_json((folder/'playback.json').read_text())
    locations=json.loads((folder/'media.json').read_text(encoding='utf-8'))
    media={m.video_filename:resolve_relative(root,locations[m.video_filename]) for r in manifest.runs for m in r.media}
    _registered[manifest.recording_id]=RecordingResources(manifest=manifest,parquet=folder/'display.parquet',videos=media)
    cloud=folder/'point_cloud'
    if (cloud/'manifest.json').is_file():_clouds[manifest.recording_id]=cloud
    return {'id':manifest.recording_id,'displayName':f'{project.project_id} - fresh pose candidates',
            'pointCloudManifest':f'/freemocap/recordings/{manifest.recording_id}/point-cloud/manifest.json' if manifest.recording_id in _clouds else None}


def camera_to_world():
    # Forge owns the canonical convention; only the camera I/O boundary is app-owned.
    canonical = CoordinateSystemRegistry.from_default_yaml().default
    optical = CoordinateSystemConvention(
        name='rectified_optical', description='Rectified image camera coordinates',
        x_direction=AnatomicalDirection.RIGHT, y_direction=AnatomicalDirection.DOWN,
        z_direction=AnatomicalDirection.FORWARD)
    return CoordinateSystemTransform(from_convention=optical, to_convention=canonical).matrix


def convert_geometry(mesh, target, authored=None):
    """Use authored points when supplied; otherwise retain explicitly derived bounds."""
    source_to_mm=1. if target.authored_units=='mm' else 1000.
    source_points=np.array(list(itertools.product(*zip(mesh.bounds[0],mesh.bounds[1]))),dtype=float)
    names=tuple('bounds_'+''.join('max' if bit else 'min' for bit in bits) for bits in itertools.product((0,1),repeat=3))
    if authored is not None:
        source_points=authored["points_mm"]/source_to_mm
        names=authored["names"]
    scale=float(np.max(mesh.extents)*source_to_mm)
    source_to_object=np.diag([source_to_mm]*3+[1.])
    rigid=build_stl_rigid_body(name=target.object_id,feature_names=names,object_positions_mm=source_points*source_to_mm,
        reference_unit_mm=scale,source_mesh_to_object_mm=source_to_object,source_mesh_units=target.authored_units,
        mesh_sha256=target.geometry.sha256)
    local=trimesh.transform_points(source_points,rigid.source_mesh_to_segment_reference)
    simplified=mesh.simplify_quadric_decimation(face_count=min(8000,len(mesh.faces))) if len(mesh.faces)>8000 else mesh.copy()
    vertices=trimesh.transform_points(simplified.vertices,rigid.source_mesh_to_segment_reference)
    edges=np.array([(a,b) for a,b in itertools.combinations(range(8),2) if (a^b) in (1,2,4)])
    if authored is not None:edges=authored["edges"]
    return rigid,source_points,local,vertices,simplified.faces,edges


def model_definition(rigid,local,vertices,faces,edges,model_id,color,opacity,authored=False):
    segment=rigid.segment_name
    return {'model_id':model_id,'scale_reference_name':rigid.scale_reference_name,
        'segments':[{'name':segment,'parent':None,'primary_axis':'z','rest_orientation':[1,0,0,0],'length_proportion':1.,'is_fully_specified':True}],
        'landmarks':[{'name':name,'rest_position':position.tolist()} for name,position in zip(rigid.feature_names,local)],
        'connections':[],'landmark_groups':[{'name':'Authored STL keypoints' if authored else 'Derived STL bounds (not detector output)','landmark_names':list(rigid.feature_names),'color':'#ff45e6' if authored else color}],
        'landmark_connections':[{'name':'Authored keypoint topology' if authored else 'STL bounds','pairs':[[rigid.feature_names[a],rigid.feature_names[b]] for a,b in edges],'color':color}],
        'object_geometry':{'feature_names':list(rigid.feature_names),'segment_name':segment,'source_mesh_units':rigid.source_mesh_units,
            'mesh_sha256':rigid.mesh_sha256,'reference_unit_mm':rigid.reference_unit_mm,
            'object_to_segment_reference':rigid.object_to_segment_reference.ravel().tolist(),
            'source_mesh_to_segment_reference':rigid.source_mesh_to_segment_reference.ravel().tolist(),
            'segment_reference_to_source_mesh':rigid.segment_reference_to_source_mesh.ravel().tolist()},
        'presentation':{'attached_lines':[{'segment':segment,'authored_length':1.,'positions':local[edges].ravel().tolist(),
            'material':{'color':color,'opacity':.65},'surfaces':[{'positions':vertices.ravel().tolist(),'indices':faces.ravel().tolist(),
            'material':{'color':color,'opacity':opacity},'double_sided':True}]}],'excluded_origin_edges':[],'excluded_bones':[segment]}}


def calibrated_cameras(cal, optical_to_world):
    """Publish camera-to-world poses and their inverse optical extrinsics in mm."""
    cameras=[]
    for index,camera in enumerate(('left','right')):
        world_from_camera=np.eye(4);world_from_camera[:3,:3]=optical_to_world
        if camera=='right':
            stereo=np.array(cal['T_left_from_right_m']);world_from_camera[:3,:3]=optical_to_world@stereo[:3,:3]
            world_from_camera[:3,3]=optical_to_world@stereo[:3,3]*1000.
        camera_from_world=np.linalg.inv(world_from_camera);K=np.array(cal[camera])
        cameras.append({'id':camera,'index':index,'image_size':[cal['image_width'],cal['image_height']],
            'intrinsics':{'fx':K[0,0],'fy':K[1,1],'cx':K[0,2],'cy':K[1,2],'k1':0.,'k2':0.,'p1':0.,'p2':0.},
            'extrinsics':{'quaternion_wxyz':RotationQuaternion.from_rotation_matrix(matrix=camera_from_world[:3,:3]).as_array().tolist(),'translation':camera_from_world[:3,3].tolist()},
            'world_position':world_from_camera[:3,3].tolist(),'world_orientation':world_from_camera[:3,:3].tolist()})
    return cameras


def build_project_playback(manifest_path: Path, *, cancelled=lambda: False):
    def check_cancelled():
        if cancelled(): raise InterruptedError("Playback preparation cancelled")
    check_cancelled()
    manifest_path=manifest_path.resolve();root=manifest_path.parent;project=read_model(manifest_path,Project)
    if not project.sample_result: raise ValueError('Prepare fresh candidates before building playback')
    result=resolve_relative(root,project.sample_result);target=load_target(root,project.target_manifests[0])
    authority=json.loads((result/'manifest.json').read_text())
    for name,identity in authority['files'].items():
        if file_digest(result/name)!=identity['sha256']: raise ValueError(f'Changed prepared artifact: {name}')
    if file_digest(resolve_relative(root,target.geometry.path))!=target.geometry.sha256:raise ValueError('Changed STL')
    rows=pq.read_table(result/'candidates.parquet').to_pylist();cal=json.loads((result/'calibration.json').read_text())
    frames=np.array([r['source_frame'] for r in rows],dtype=np.int64);times_ns=np.array([r['timestamp_ns'] for r in rows],dtype=np.int64)
    # Small relative seconds for display; exact source clock remains in authoritative Parquet/provenance.
    times=(times_ns-times_ns[0]).astype(np.float64)/1e9
    if not np.array_equal(frames,np.arange(frames[0],frames[0]+len(frames))):raise ValueError('Video adapter requires a contiguous source span')
    authored=load_authored_geometry(root,target)
    mesh=trimesh.load_mesh(resolve_relative(root,target.geometry.path));rigid,source_points,local,vertices,faces,edges=convert_geometry(mesh,target,authored)
    optical_to_world=camera_to_world();n=len(rows);source_to_mm=1. if target.authored_units=='mm' else 1000.
    poses=np.full((n,4,4),np.nan);accepted=np.array([r['accepted'] for r in rows])
    for i,row in enumerate(rows):
        if row.get('T_left_from_stl_m') is None:continue
        pose=np.array(row['T_left_from_stl_m']);poses[i]=np.eye(4)
        poses[i,:3,:3]=optical_to_world@pose[:3,:3]*source_to_mm
        poses[i,:3,3]=optical_to_world@pose[:3,3]*1000.
    paths=recording_structure(root,authority['descriptor']['recording_id'])
    extension=paths.application_dir('skellyclicker')
    playback_id='playback-'+uuid4().hex[:12];work=extension/'working/playback'/playback_id;work.mkdir(parents=True)
    scene_frame={'name':'blender_world','basis':'blender_x_right_y_forward_z_up','units':'mm',
                 'alignment':None,'additional_transform':None}
    group='stereo';clock=RecordingTimeline(sensor_group=group,source='timing:'+group,frame_numbers=tuple(frames.tolist()),timestamps_s=tuple(times.tolist()))
    models=[];channels=[];samples=[];statics=[];sources={}
    for label,color,mask,reference in [('candidate_pass','#5ce69a',accepted,False),('candidate_rejected','#ffa244',~accepted,False),('authored_reference','#b99aff',np.ones(n,bool),True)]:
        model_id=target.object_id+'_'+label;sources[label]=model_id
        models.append(model_definition(rigid,local,vertices,faces,edges,model_id,color,.5 if not reference else .25,authored is not None))
        source_poses=poses.copy()
        if reference:source_poses=np.repeat(np.diag([source_to_mm]*3+[1.])[None],n,axis=0)
        source_poses[~mask]=np.nan
        segment_poses=source_poses@rigid.segment_reference_to_source_mesh
        positions=np.einsum('fij,nj->fni',source_poses[:,:3,:3],source_points)+source_poses[:,None,:3,3]
        quats=np.full((n,1,4),np.nan)
        for i in range(n):
            if np.isfinite(segment_poses[i]).all():quats[i,0]=RotationQuaternion.from_rotation_matrix(matrix=segment_poses[i,:3,:3]/rigid.reference_unit_mm).as_array()
        for kind,names,components,values in [
            ('LANDMARKS_3D',rigid.feature_names,{'x':'mm','y':'mm','z':'mm'},positions),
            ('SEGMENT_ORIGINS',(rigid.segment_name,),{'x':'mm','y':'mm','z':'mm'},segment_poses[:,None,:3,3]),
            ('ROTATIONS_WORLD',(rigid.segment_name,),{'w':'1','x':'1','y':'1','z':'1'},quats)]:
            channel=RecordingChannel(sensor_group=group,source=label,reference_frame=scene_frame['name'],kind=kind,names=names,components=components)
            channels.append(channel);samples.append(ChannelSamples(run_id=0,channel=channel,frame_numbers=frames,timestamps_s=times,values=values))
        for kind,name,component in [('MODEL_SCALE','object','scale'),('SEGMENT_LENGTHS',rigid.segment_name,'length')]:
            channel=RecordingChannel(sensor_group=group,source=label,reference_frame=scene_frame['name'],kind=kind,names=(name,),components={component:'mm'})
            statics.append({'channel':channel.model_dump(mode='json'),'values':{name:{component:rigid.reference_unit_mm}}})
    outlines=project_authored_geometry(authored,rows,cal,work,check_cancelled) if authored else None
    media=[];media_locations={};media_hashes={};fps=float(cal['nominal_fps']);ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:raise RuntimeError('ffmpeg is required for buffered playback media')
    for camera in ('left','right'):
        check_cancelled()
        camera_clock=RecordingTimeline(sensor_group=group,source=camera,frame_numbers=tuple(frames.tolist()),timestamps_s=tuple(times.tolist()))
        annotated=work/('annotated-'+camera);annotated.mkdir()
        projections=iter(camera_projections(outlines,camera)) if outlines else None
        for row in rows:
            check_cancelled()
            frame=row['source_frame'];suffix='' if authored else '-candidate'
            image=Image.open(result/'frames'/f'{frame:06d}-{camera}{suffix}.png').convert('RGB');draw=ImageDraw.Draw(image)
            projection=None
            if projections is not None:
                projected_frame,projection=next(projections)
                if projected_frame!=frame:raise ValueError('Authored outline frame ordering mismatch')
            matrix=row.get('T_'+camera+'_from_stl_m')
            if matrix is not None:
                pose=np.array(matrix);points=source_points*(.001 if target.authored_units=='mm' else 1.)
                camera_points=points@pose[:3,:3].T+pose[:3,3];pixels=camera_points@np.array(cal[camera]).T;pixels=pixels[:,:2]/pixels[:,2:]
                color='#5ce69a' if row['accepted'] else '#ffa244'
                if authored:
                    # Independently verify original-STL transform against recovered centered-mesh projector.
                    if not np.allclose(pixels,projection['keypoints_xy'],atol=.001):raise ValueError('Authored projection frame mismatch')
                    for segment in projection['mesh_wireframe_segments_xy']:
                        draw.line([tuple(p) for p in segment],fill='#37eaff',width=1)
                    for (x,y),visible in zip(pixels,projection['visibility']):
                        if visible:draw.ellipse((x-2,y-2,x+2,y+2),fill='#ff45e6',outline='#161027',width=1)
                        else:draw.ellipse((x-2,y-2,x+2,y+2),outline='#ff45e6',width=1)
                else:
                    for x,y in pixels:draw.ellipse((x-2,y-2,x+2,y+2),fill=color)
                    for a,b in edges:draw.line([tuple(pixels[a]),tuple(pixels[b])],fill=color,width=1)
            image.save(annotated/f'{frame:06d}.png',compress_level=1)
        if projections is not None:
            if next(projections,None) is not None:raise ValueError('Unexpected extra authored projection')
            projections.close()
        for source,pattern in [('synchronized',str(result/'frames'/('%06d-'+camera+'.png'))),('annotated',str(annotated/'%06d.png'))]:
            check_cancelled()
            filename=source+'-'+camera+'.mp4';destination=work/filename
            command=[ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-framerate',str(fps),'-start_number',str(frames[0]),'-i',pattern,'-frames:v',str(n),'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-g','15','-movflags','+faststart',str(destination)]
            subprocess.run(command,check=True,stdin=subprocess.DEVNULL,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW if __import__('os').name=='nt' else 0)
            media.append(PlaybackMedia(video_source=source,video_filename=filename,nominal_fps=fps,timeline=camera_clock))
            logger.info('Encoded %s: %d frames for buffered SDK playback',filename,n)
    cameras=calibrated_cameras(cal,optical_to_world)
    run=PlaybackRun(run_id=0,reference_frames={scene_frame['name']:scene_frame},
        scene_reference_frames={group:scene_frame['name']},model_sources=sources,models=tuple(models),channels=tuple(channels),static_channels=tuple(statics),timelines=(clock,),media=tuple(media),camera_geometry={group:tuple(cameras)})
    manifest=PlaybackManifest(recording_id=playback_id,revision=playback_id,selected_run_id=0,runs=(run,))
    provenance={'source_result':project.sample_result,'source_manifest_sha256':file_digest(result/'manifest.json'),'source_timestamp_origin_ns':str(times_ns[0]),'source_timestamps_ns':[str(x) for x in times_ns],
        'display_world':'Blender +X right +Y forward +Z up, mm; optical-to-world conversion once','optical_to_world':optical_to_world.tolist(),
        'keypoints':'Exact authored STL keypoints; pose-projected, not detector output or approved training labels' if authored else 'Derived STL bounding-box source_points; not detector output or approved training labels',
        'authored_geometry':{'manifest_sha256':authored['manifest_sha256'],'definition':authored['manifest'],'point_names':list(authored['names']),'outline':'Original dense mesh crease/silhouette projector with BVH self-visibility; external occlusion unknown'} if authored else None,'reference':'Unposed STL authored frame at world origin; comparison reference, not measured pose',
        'candidate_status':{str(r['source_frame']):r['status'] for r in rows},'human_review':'unreviewed','surface_simplified_faces':len(faces),'source_geometry_sha256':target.geometry.sha256,'encoded_fps':fps,'encoded_frame_indices':'0..N-1 map in order to source_frame_numbers, never substitute for source identities'}
    write_playback(path=work/'display.parquet',manifest=manifest,samples=samples,provenance=provenance,cancelled=cancelled)
    atomic_json(work/'playback.json',manifest.model_dump(mode='json'));atomic_json(work/'provenance.json',provenance)
    # Sample videos live below explicit clip directories, never alongside the full
    # synchronized inputs that Core enumerates. Each publication has unique paths.
    for entry in media:
        base=paths.videos_synchronized_dir if entry.video_source=='synchronized' else paths.videos_annotated_dir
        clip=base/'clips'/playback_id
        clip.mkdir(parents=True,exist_ok=True)
        video=work/entry.video_filename
        destination_video=clip/entry.video_filename
        if destination_video.exists():raise FileExistsError(destination_video)
        shutil.copyfile(video,destination_video)
        if file_digest(video)!=file_digest(destination_video):raise ValueError('Published video hash mismatch')
        media_locations[entry.video_filename]=destination_video.relative_to(root).as_posix()
        media_hashes[entry.video_filename]={'sha256':file_digest(destination_video),'bytes':destination_video.stat().st_size}
        video.unlink()  # Only this attempt's newly encoded staging file; published media is retained.
    atomic_json(work/'media.json',media_locations)
    atomic_json(work/'media_hashes.json',media_hashes)
    if (result/'point_cloud/manifest.json').is_file():
        from .point_cloud import write_display_clouds
        write_display_clouds(result/'point_cloud',work/'point_cloud',revision=playback_id,
            reference_frame={'id':scene_frame['name'],'definition':scene_frame},cancelled=cancelled)
    atomic_json(work/'inventory.json',{k:v.model_dump() for k,v in inventory(work).items()})
    relative=(extension/'playback'/playback_id).relative_to(root).as_posix();destination=resolve_relative(root,relative);destination.parent.mkdir(exist_ok=True)
    with project_lock(root):
        check_cancelled()
        project=read_model(manifest_path,Project)
        publish_directory(staging=work,destination=destination);project.playback_result=relative;atomic_json(manifest_path,project.model_dump(mode='json'))
    logger.info('SDK recording ready: %s, actual STL surfaces and %d timed samples',playback_id,n)
    return register_project(root,project)

if __name__=='__main__':
    import sys
    print(json.dumps(build_project_playback(Path(sys.argv[1]))))
