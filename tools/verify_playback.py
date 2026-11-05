"""Audit a generated playback revision against its authoritative fresh pose result."""
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import trimesh
from PIL import Image, ImageDraw
import pyarrow.compute as pc
import pyarrow.parquet as pq
from freemocap_sdk.storage import file_digest
from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion

root=Path(sys.argv[1]);project=json.loads(next(root.glob('*_project.json')).read_text());folder=root/project['playback_result'];result=root/project['sample_result']
manifest=json.loads((folder/'playback.json').read_text());run=manifest['runs'][0];provenance=json.loads((folder/'provenance.json').read_text());cal=json.loads((result/'calibration.json').read_text());rows=pq.read_table(result/'candidates.parquet').to_pylist();table=pq.read_table(folder/'display.parquet');M=np.array(provenance['optical_to_world']);maximum=0.;maximum_projection=0.
# Physical camera expectations are independent of the adapter's conversion helper.
# The rectified left camera defines the origin, forward +Y and image-up +Z.
cameras={camera['id']:camera for camera in run['camera_geometry']['stereo']}
np.testing.assert_allclose(cameras['left']['world_position'],[0,0,0],atol=1e-9)
for camera in cameras.values():
 rotation=np.array(camera['world_orientation'])
 np.testing.assert_allclose(rotation@[0,0,1],[0,1,0],atol=1e-9)
 np.testing.assert_allclose(rotation@[0,-1,0],[0,0,1],atol=1e-9)
np.testing.assert_allclose(cameras['right']['world_position'],[119.76435035467148,0,0],atol=1e-6)
target=json.loads((root/project['target_manifests'][0]).read_text())
mesh=trimesh.load_mesh(root/target['geometry']['path'])
mesh_m=np.asarray(mesh.vertices)*(.001 if target['authored_units']=='mm' else 1.)
scene_checks=[];panels=[]
for frame in (12,21):
 row=next(row for row in rows if row['source_frame']==frame)
 pose=np.array(row['T_left_from_stl_m']);optical=mesh_m@pose[:3,:3].T+pose[:3,3]
 # Explicit axis expectation, not reading the matrix written by the producer.
 world=np.column_stack((optical[:,0],optical[:,2],-optical[:,1]))*1000.
 for name,camera in cameras.items():
  extr=camera['extrinsics'];rotation=RotationQuaternion.from_array(array=np.array(extr['quaternion_wxyz'])).to_rotation_matrix()
  in_camera=world@rotation.T+np.array(extr['translation'])
  assert np.min(in_camera[:,2])>0,(frame,name,'mesh behind camera')
  expected_pose=np.array(row['T_'+name+'_from_stl_m']);expected=mesh_m@expected_pose[:3,:3].T+expected_pose[:3,3]
  np.testing.assert_allclose(in_camera,expected*1000.,atol=1e-3)
  K=np.array(cal[name]);uv=in_camera@K.T;uv=uv[:,:2]/uv[:,2:]
  # Use actual raw images with full mesh silhouette projection as review evidence.
  image=Image.open(result/'frames'/f'{frame:06d}-{name}.png').convert('RGB');draw=ImageDraw.Draw(image)
  for x,y in uv:draw.point((float(x),float(y)),fill='#5ce69a' if row['accepted'] else '#ffa244')
  draw.text((15,15),f"Source {frame} / {name} / {row['status']} / full STL through published camera",fill='white')
  image.thumbnail((640,360));panels.append(image)
  scene_checks.append({'frame':frame,'camera':name,'status':row['status'],'minimum_depth_mm':float(in_camera[:,2].min()),'projected_bounds_px':[uv.min(axis=0).tolist(),uv.max(axis=0).tolist()]})
contact=Image.new('RGB',(1280,720))
for i,panel in enumerate(panels):contact.paste(panel,((i%2)*640,(i//2)*360))
output=Path(__file__).resolve().parents[1]/'.test-artifacts/scene-coordinate-projections.png';contact.save(output)
for model in run['models']:
 if model['model_id'].endswith('authored_reference'):continue
 source=next(k for k,v in run['model_sources'].items() if v==model['model_id']);scale=model['object_geometry']['reference_unit_mm'];inverse=np.array(model['object_geometry']['segment_reference_to_source_mesh']).reshape(4,4)
 local=np.array([point['rest_position'] for point in model['landmarks']]);original=(np.c_[local,np.ones(len(local))]@inverse.T)[:,:3];factor=.001 if model['object_geometry']['source_mesh_units']=='mm' else 1.
 def values(kind,width):
  selection=pc.and_(pc.equal(table['source'],source),pc.equal(table['channel'],kind));return np.array(table.filter(selection)['value'].to_pylist(),dtype=float).reshape(len(rows),width)
 origins=values('SEGMENT_ORIGINS',3);quats=values('ROTATIONS_WORLD',4);points=values('LANDMARKS_3D',len(local)*3).reshape(len(rows),len(local),3)
 for i,row in enumerate(rows):
  active=bool(row['accepted'])==source.endswith('_pass')
  if not active:
   assert np.isnan(origins[i]).all() and np.isnan(quats[i]).all() and np.isnan(points[i]).all();continue
  R=RotationQuaternion.from_array(array=quats[i]).to_rotation_matrix();display=local@R.T*scale+origins[i]
  maximum=max(maximum,float(np.max(abs(display-points[i]))))
  left=display@M/1000.
  for camera in ('left','right'):
   current=left
   if camera=='right':
    right_from_left=np.linalg.inv(cal['T_left_from_right_m']);current=left@right_from_left[:3,:3].T+right_from_left[:3,3]
   pose=np.array(row['T_'+camera+'_from_stl_m']);expected=(original*factor)@pose[:3,:3].T+pose[:3,3]
   maximum=max(maximum,float(np.max(abs(current-expected)))*1000.)
   K=np.array(cal[camera]);a=current@K.T;b=expected@K.T
   maximum_projection=max(maximum_projection,float(np.max(abs(a[:,:2]/a[:,2:]-b[:,:2]/b[:,2:]))))
# FoundationPose supplies float32 matrices; conversion to unit quaternions removes their tiny orthogonality error.
assert maximum<1e-3 and maximum_projection<1e-3,(maximum,maximum_projection)
media_locations=json.loads((folder/'media.json').read_text(encoding='utf-8'))
media_hashes=json.loads((folder/'media_hashes.json').read_text(encoding='utf-8'))
for media in run['media']:
 video=root/media_locations[media['video_filename']]
 assert file_digest(video)==media_hashes[media['video_filename']]['sha256']
 data=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=nb_frames,width,height,r_frame_rate','-of','json',str(video)]))['streams'][0]
 assert int(data['nb_frames'])==len(rows) and data['width']==cal['image_width'] and data['height']==cal['image_height'] and data['r_frame_rate']=='30/1',data
for name,value in json.loads((folder/'inventory.json').read_text()).items():assert file_digest(folder/name)==value['sha256'],name
print(json.dumps({'frames':len(rows),'encoded_videos':len(run['media']),'max_world_error_mm':maximum,'max_reprojection_error_px':maximum_projection,'source_frame_mapping':run['timelines'][0]['frame_numbers'],'hashes_verified':True,'scene_checks':scene_checks,'projection_evidence':str(output)}))
