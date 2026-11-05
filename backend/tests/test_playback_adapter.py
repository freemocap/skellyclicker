"""Verify the display adapter's measured geometry, not merely its encoded schema."""
import unittest
import numpy as np
import trimesh
from skellyclicker_app.playback_adapter import convert_geometry,camera_to_world,calibrated_cameras,build_project_playback
from skellyclicker_app.projects import Target,Artifact
from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion
from pathlib import Path

class PlaybackAdapterTest(unittest.TestCase):
 def test_arbitrary_mesh_units_and_segment_transform(self):
  for units,size in [('mm',1.),('m',.001)]:
   mesh=trimesh.creation.box(extents=np.array([70.,30.,45.])*size);mesh.apply_translation(np.array([15.,-8.,22.])*size)
   target=Target(object_id='arbitrary-object',geometry=Artifact(path='mesh.stl',bytes=0,sha256='0'*64),authored_units=units,source_path='source.stl')
   rigid,corners,local,vertices,faces,edges=convert_geometry(mesh,target)
   source_to_mm=1. if units=='mm' else 1000.
   rotation=RotationQuaternion.from_components(w=.9,x=.1,y=.2,z=.3).to_rotation_matrix()
   source_pose=np.eye(4);source_pose[:3,:3]=camera_to_world()@rotation*source_to_mm;source_pose[:3,3]=[15.,450.,85.]
   segment_pose=source_pose@rigid.segment_reference_to_source_mesh
   segment_rotation=segment_pose[:3,:3]/rigid.reference_unit_mm
   np.testing.assert_allclose(segment_rotation.T@segment_rotation,np.eye(3),atol=1e-12)
   expected=trimesh.transform_points(corners,source_pose)
   actual=local@segment_rotation.T*rigid.reference_unit_mm+segment_pose[:3,3]
   np.testing.assert_allclose(actual,expected,atol=1e-10)
   np.testing.assert_allclose(rigid.source_mesh_to_segment_reference@rigid.segment_reference_to_source_mesh,np.eye(4),atol=1e-12)
   self.assertEqual(len(edges),12)
 def test_optical_boundary_and_nonidentity_stereo_pose(self):
  # Independent geometric expectations: optical right->world right, optical
  # forward->world forward, optical image down->world down. No renderer offsets.
  M=camera_to_world()
  np.testing.assert_allclose(M@[1,0,0],[1,0,0],atol=1e-12)
  np.testing.assert_allclose(M@[0,0,1],[0,1,0],atol=1e-12)
  np.testing.assert_allclose(M@[0,-1,0],[0,0,1],atol=1e-12)
  # Deliberately nonidentity camera rotation: right optical forward becomes
  # left optical right, making inverse/composition mistakes observable.
  stereo=np.array([[0,0,1,.12],[0,1,0,.02],[-1,0,0,.03],[0,0,0,1.]])
  cal={'left':[[500,0,310],[0,510,230],[0,0,1]],'right':[[500,0,310],[0,510,230],[0,0,1]],
       'image_width':640,'image_height':480,'T_left_from_right_m':stereo.tolist()}
  left,right=calibrated_cameras(cal,M)
  np.testing.assert_allclose(right['world_position'],[120,30,-20],atol=1e-10)
  np.testing.assert_allclose(np.array(right['world_orientation'])@[0,0,1],[1,0,0],atol=1e-12)
  # Point 500mm ahead of right camera: camera extrinsics must recover +Z depth.
  world=np.array([620,30,-20.])
  q=RotationQuaternion.from_array(array=np.array(right['extrinsics']['quaternion_wxyz']))
  np.testing.assert_allclose(q.to_rotation_matrix()@world+right['extrinsics']['translation'],[0,0,500],atol=1e-10)
  np.testing.assert_allclose(left['world_position'],[0,0,0],atol=1e-12)

 def test_cancel_before_any_files_are_touched(self):
  with self.assertRaises(InterruptedError):build_project_playback(Path('this-does-not-exist.json'),cancelled=lambda:True)

if __name__=='__main__':unittest.main()
