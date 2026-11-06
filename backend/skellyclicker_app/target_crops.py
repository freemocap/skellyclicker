"""Compact crop metadata derived from the published target projection, never a new fit."""
import json
from functools import lru_cache
import numpy as np
from freemocap_sdk.storage import file_digest, resolve_relative
from .projects import load_target
from .authored_geometry import load_authored_geometry


def projection_bounds(projection, width, height):
    if not projection or not projection.get('positive_depth'): return None
    points=[]
    for name in ('keypoints_xy','mesh_wireframe_segments_xy'):
        value=projection.get(name)
        if value: points.append(np.asarray(value,dtype=float).reshape(-1,2))
    if not points:return None
    xy=np.concatenate(points)
    if not np.isfinite(xy).all():return None
    low=xy.min(axis=0);high=xy.max(axis=0)
    # An off-image object must not turn into a crop of unrelated edge pixels.
    if high[0]<=0 or high[1]<=0 or low[0]>=width or low[1]>=height:return None
    padding=np.maximum((high-low)*.2,16.)
    low=np.maximum(low-padding,0);high=np.minimum(high+padding,[width,height])
    if np.any(high<=low):return None
    return dict(x=float(low[0]),y=float(low[1]),width=float(high[0]-low[0]),height=float(high[1]-low[1]))


@lru_cache(maxsize=4)
def compact_projection(path, digest, size, modified_ns, width, height):
    # The stat identity invalidates cached data; the content identity verifies it.
    if path.stat().st_size!=size or file_digest(path)!=digest:raise ValueError('Changed target projection')
    cameras={'left':{},'right':{}}
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line);camera=row['camera'];frame=str(row['source_frame'])
            if camera not in cameras or frame in cameras[camera]:raise ValueError('Invalid projection camera/frame identity')
            cameras[camera][frame]=projection_bounds(row['projection'],width,height)
    return cameras


def target_crop_metadata(root, project, recording_id):
    folder=resolve_relative(root,project.playback_result)
    identities=json.loads((folder/'inventory.json').read_text())
    provenance_path=folder/'provenance.json'
    if file_digest(provenance_path)!=identities['provenance.json']['sha256']:raise ValueError('Changed playback provenance')
    provenance=json.loads(provenance_path.read_text())
    target=load_target(root,project.target_manifests[0]);authored=load_authored_geometry(root,target)
    if not authored:raise ValueError('No published target outline')
    source=resolve_relative(root,project.sample_result)
    old=provenance.get('authored_geometry',{}).get('definition',{})
    if (provenance['source_manifest_sha256']!=file_digest(source/'manifest.json')
        or provenance['source_geometry_sha256']!=target.geometry.sha256
        or file_digest(resolve_relative(root,target.geometry.path))!=target.geometry.sha256
        or any(old.get(k,{}).get('sha256')!=authored['manifest'][k]['sha256'] for k in ('keypoints','outline'))
        or old.get('origin_mm')!=authored['manifest']['origin_mm']):raise ValueError('Target and published playback differ')
    authority=json.loads((source/'manifest.json').read_text());cal_path=source/'calibration.json'
    if file_digest(cal_path)!=authority['files']['calibration.json']['sha256']:raise ValueError('Changed calibration')
    cal=json.loads(cal_path.read_text());width=cal['image_width'];height=cal['image_height']
    path=folder/'outline-projections.jsonl';identity=identities['outline-projections.jsonl'];stat=path.stat()
    cameras=compact_projection(path,identity['sha256'],identity['bytes'],stat.st_mtime_ns,width,height)
    media=json.loads((folder/'playback.json').read_text())
    filenames={m['video_filename']:camera for run in media['runs'] for m in run['media'] for camera in cameras
               if m['video_filename'] in (f'annotated-{camera}.mp4',f'synchronized-{camera}.mp4')}
    return dict(recording_id=recording_id,width=width,height=height,filenames=filenames,cameras=cameras,
                projection_sha256=identity['sha256'],stl_sha256=target.geometry.sha256)
