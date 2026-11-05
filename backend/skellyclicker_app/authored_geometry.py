"""Hash-bound authored points and dense outline geometry, independent of fitted results."""
import json
import shutil
import subprocess
from pathlib import Path
import numpy as np
from freemocap_sdk.storage import file_digest,resolve_relative,atomic_json


def load_authored_geometry(root,target):
    if target.authored_geometry is None:return None
    def checked(artifact):
        path=resolve_relative(root,artifact['path'])
        if file_digest(path)!=artifact['sha256']:raise ValueError('Changed authored geometry artifact')
        return path
    manifest=checked(target.authored_geometry.model_dump())
    spec=json.loads(manifest.read_text(encoding='utf-8'))
    points_path=checked(spec['keypoints']);asset=checked(spec['outline'])
    definition=json.loads(points_path.read_text(encoding='utf-8'))
    if definition['units']!='mm' or definition['source_stl_sha256']!=target.geometry.sha256 or spec['source_stl_sha256']!=target.geometry.sha256:
        raise ValueError('Authored definition does not match target STL/units')
    points=np.asarray([p['xyz_mm'] for p in definition['points']],dtype=float)
    names=tuple(p['group']+' / '+p['name'] for p in definition['points'])
    if points.shape!=(len(names),3) or len(names)<3 or len(set(names))!=len(names) or not np.isfinite(points).all():
        raise ValueError('Authored points must be finite, distinct named 3D points')
    edges=[]
    for group in definition['connections']:
        ids=group['ids']
        if len(ids)<2 or any(type(i)!=int or not 0<=i<len(names) for i in ids):raise ValueError('Invalid authored topology')
        edges.extend(zip(ids,ids[1:]))
        if group['closed']:edges.append((ids[-1],ids[0]))
    origin=np.asarray(spec['origin_mm'],dtype=float)
    if origin.shape!=(3,) or not np.isfinite(origin).all():raise ValueError('Invalid outline origin')
    return dict(names=names,points_mm=points,edges=np.asarray(edges,dtype=int).reshape(-1,2),
        asset=asset,origin_mm=origin.tolist(),manifest=spec,manifest_sha256=file_digest(manifest),definition=definition)


def project_authored_geometry(authored,rows,cal,work,check_cancelled):
    node=shutil.which('node')
    if not node:raise RuntimeError('Node is required for authored mesh outline preparation')
    poses=work/'outline-poses.jsonl';output=work/'outline-projections.jsonl'
    with poses.open('w',encoding='utf-8') as f:
        for row in rows:
            for camera in ('left','right'):
                f.write(json.dumps(dict(source_frame=row['source_frame'],camera=camera,pose=row.get('T_'+camera+'_from_stl_m')))+'\n')
    request=work/'outline-request.json'
    atomic_json(request,dict(asset=str(authored['asset']),names=authored['names'],points_mm=authored['points_mm'].tolist(),
        origin_mm=authored['origin_mm'],poses=str(poses),output=str(output),cameras={c:cal[c] for c in ('left','right')}))
    with (work/'outline.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen([node,str(Path(__file__).parent/'workers/project_authored.cjs'),str(request)],
            stdout=log,stderr=log,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if __import__('os').name=='nt' else 0)
        try:
            while True:
                check_cancelled()
                try:code=process.wait(timeout=.2);break
                except subprocess.TimeoutExpired:pass
            if code:raise RuntimeError('Authored outline projection failed: '+str(work/'outline.log'))
        finally:
            if process.poll() is None:process.terminate();process.wait()
    return output


def camera_projections(path,camera):
    """Stream one projection at a time; dense outlines never become a clip-sized Python object graph."""
    with path.open(encoding='utf-8') as f:
        for line in f:
            item=json.loads(line)
            if item['camera']==camera:yield item['source_frame'],item['projection']
