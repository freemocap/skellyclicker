"""Object-frame viewing directions and equal-solid-angle sampling, independent of render view."""
import math
from functools import lru_cache
import numpy as np
import trimesh
from .label_inputs import checked

@lru_cache(maxsize=8)
def mesh_frame(path,digest,size,modified_ns,units):
    checked(path,{'sha256':digest,'bytes':size})
    scale={'mm':.001,'m':1.0}[units]
    mesh=trimesh.load_mesh(path,process=False);bounds=np.asarray(mesh.bounds,dtype=float)*scale
    if bounds.shape!=(2,3) or not np.isfinite(bounds).all():raise ValueError('STL has invalid bounds')
    center=bounds.mean(axis=0);radius=float(np.linalg.norm(bounds[1]-bounds[0])/2)
    if radius<=0:raise ValueError('STL has zero extent')
    return center.tolist(),radius*1.3,scale

def viewing_direction(transform,center):
    try:
        T=np.asarray(transform,dtype=float);c=np.asarray(center,dtype=float)
        if T.shape!=(4,4) or c.shape!=(3,) or not np.isfinite(T).all() or not np.isfinite(c).all():return None
        R=T[:3,:3]
        if not np.allclose(T[3],[0,0,0,1],atol=1e-7,rtol=0) or not np.allclose(R.T@R,np.eye(3),atol=1e-4,rtol=0) or not math.isclose(float(np.linalg.det(R)),1,abs_tol=1e-4):return None
        vector=-R.T@T[:3,3]-c;length=float(np.linalg.norm(vector))
        if length<=1e-9:return None
        return (vector/length).tolist()
    except (TypeError,ValueError):return None

def spherical_bin(direction,azimuth_bins,z_bins):
    x,y,z=direction
    phi=0 if math.hypot(x,y)<1e-12 else math.atan2(y,x)%(2*math.pi)
    zi=min(z_bins-1,max(0,int((z+1)*.5*z_bins)))
    pi=min(azimuth_bins-1,int(phi/(2*math.pi)*azimuth_bins))
    return zi*azimuth_bins+pi

def coverage_pool(rows,azimuth_bins,z_bins):
    counts=[0]*(azimuth_bins*z_bins);samples=[]
    for row in rows:
        view=row['viewpoint']
        if view is not None:
            counts[view['bin']]+=1;samples.append({'image_id':row['image_id'],**view})
    return {'count':len(rows),'known_count':len(samples),'unknown_count':len(rows)-len(samples),'occupied_bins':sum(n>0 for n in counts),'counts':counts,'samples':samples}

def select_viewpoints(rows,request):
    # One queue per cell; balanced occupancy first, quality within each cell.
    from collections import deque
    from heapq import heappush,heappop
    from bisect import bisect_left,insort
    groups={};occupancy={};stamps={};chosen=[];heap=[]
    ranked=sorted((r for r in rows if r['eligible']),key=lambda r:(-r['score'],r['source_frame'],r['camera_id'],r['image_id']))
    for row in ranked:
        cell=row['viewpoint']['bin'] if request.selection_mode=='quality_viewpoints' else 0
        groups.setdefault(cell,deque()).append(row)
    def push(cell):
        if groups[cell]:
            r=groups[cell][0];heappush(heap,(occupancy.get(cell,0),-r['score'],r['source_frame'],r['camera_id'],r['image_id'],cell))
    for cell in groups:push(cell)
    while heap and len(chosen)<request.top_n:
        *_,cell=heappop(heap);row=groups[cell].popleft();stamp=int(row['timestamp_ns']);times=stamps.setdefault(row['camera_id'],[])
        i=bisect_left(times,stamp);gap=request.spacing_seconds*1e9
        spaced=not gap or ((i==0 or stamp-times[i-1]>=gap) and (i==len(times) or times[i]-stamp>=gap))
        if spaced:
            chosen.append(row['image_id']);insort(times,stamp);occupancy[cell]=occupancy.get(cell,0)+1
        push(cell)
    return chosen
