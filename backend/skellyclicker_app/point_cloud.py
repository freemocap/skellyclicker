"""Vectorized stereo-depth projection; app-owned data in the shared world frame."""
import json
import time
import numpy as np
from PIL import Image
from freemocap_sdk.storage import atomic_json
from .playback_adapter import camera_to_world


def project_depth(depth, rgb, intrinsics, optical_to_world, *, stride=4, near_m=.17, far_m=3.):
    # A regular image grid bounds density without constructing per-point objects.
    v,u=np.mgrid[0:depth.shape[0]:stride,0:depth.shape[1]:stride]
    z=depth[::stride,::stride]
    valid=np.isfinite(z)&(z>=near_m)&(z<=far_m)
    z=z[valid];u=u[valid];v=v[valid]
    K=np.asarray(intrinsics)
    optical=np.column_stack(((u-K[0,2])*z/K[0,0],(v-K[1,2])*z/K[1,1],z))
    positions=np.ascontiguousarray((optical@optical_to_world.T)*1000.,dtype='<f4')
    colors=np.ascontiguousarray(rgb[::stride,::stride][valid],dtype=np.uint8)
    return positions,colors


def write_clouds(job, update):
    output=job['output'];folder=output/'point_cloud';folder.mkdir()
    samples=json.loads((output/'samples.json').read_text(encoding='utf-8'))
    cal=json.loads((output/'calibration.json').read_text(encoding='utf-8'))
    M=camera_to_world();entries=[];started=time.monotonic()
    for index,sample in enumerate(samples):
        if job['cancel'].is_set():raise InterruptedError('Point-cloud preparation cancelled')
        tag=f"{sample['source_frame']:06d}"
        depth=np.load(output/'frames'/f'{tag}-depth.npy',allow_pickle=False)
        rgb=np.asarray(Image.open(output/'frames'/f'{tag}-left.png').convert('RGB'))
        positions,colors=project_depth(depth,rgb,cal['left'],M)
        np.savez(folder/(tag+'.npz'),positions=positions,colors=colors)
        entries.append({**sample,'path':tag+'.npz','point_count':len(positions)})
        update(job,stage='project stereo depth',completed=index+1,total=len(samples))
    atomic_json(folder/'manifest.json',{'schema_version':1,'reference_frame':{'name':'blender_world','basis':'blender_x_right_y_forward_z_up','units':'mm','alignment':None,'additional_transform':None},
       'source':'left rectified RGB and ZED NEURAL stereo depth','source_sha256':job['request']['source_sha256'],
       'sampling':{'pixel_stride':4,'near_m':.17,'far_m':3.,'invalid_depth':'omitted'},
       'position_dtype':'float32','color_dtype':'uint8','color_order':'RGB','frames':entries,'projection_seconds':time.monotonic()-started})


def write_display_clouds(source, destination, *, revision, reference_frame, cancelled=lambda:False):
    """Pack independently described bounded chunks; archive projection stays unchanged."""
    import struct
    manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    destination.mkdir(parents=True)
    origin=int(manifest['frames'][0]['timestamp_ns']);timeline=[];chunks=[]
    counts=[];chunk_size=15;maximum=25000
    for first in range(0,len(manifest['frames']),chunk_size):
        if cancelled():raise InterruptedError('Cloud publication cancelled')
        entries=[];payload=bytearray();chunk_index=len(chunks)
        for offset,row in enumerate(manifest['frames'][first:first+chunk_size]):
            with np.load(source/row['path'],allow_pickle=False) as arrays:
                positions=arrays['positions'];colors=arrays['colors']
                if len(positions)>maximum:
                    chosen=np.linspace(0,len(positions)-1,maximum,dtype=np.int64)
                    positions=positions[chosen];colors=colors[chosen]
                positions=np.ascontiguousarray(positions,dtype='<f4');colors=np.ascontiguousarray(colors,dtype=np.uint8)
                if not np.isfinite(positions).all():raise ValueError('Nonfinite display cloud')
                frame={'frame_index':first+offset,'source_frame_index':row['source_frame'],
                    'timestamp_s':(int(row['timestamp_ns'])-origin)/1e9,'timestamp_ns':str(row['timestamp_ns'])}
                timeline.append({**frame,'chunk_index':chunk_index})
                payload.extend(b'\0'*((-len(payload))%4));position_offset=len(payload);payload.extend(positions.tobytes())
                color_offset=len(payload);payload.extend(colors.tobytes())
                entries.append({**frame,'point_count':len(positions),'positions_offset':position_offset,'colors_offset':color_offset})
                counts.append(len(positions))
        header=json.dumps({'schema_version':1,'revision':revision,'reference_frame':reference_frame,'frames':entries},separators=(',',':')).encode('utf-8')
        content=struct.pack('<I',len(header))+header+b'\0'*((-(4+len(header)))%4)+payload
        name=f'chunk-{chunk_index:04d}.bin';(destination/name).write_bytes(content)
        chunks.append({'url':name,'byte_length':len(content)})
    output={'schema_version':1,'revision':revision,'reference_frame':reference_frame,'max_points':maximum,'frames':timeline,'chunks':chunks}
    atomic_json(destination/'manifest.json',output)
    atomic_json(destination/'provenance.json',{'source_manifest_sha256':__import__('hashlib').sha256((source/'manifest.json').read_bytes()).hexdigest(),
        'sampling':'uniform index subsample of finite stride4 image-grid points when over25000',
        'point_counts':counts,'source':manifest['source'],'source_sha256':manifest['source_sha256'],'projection_sampling':manifest['sampling']})
    return output
