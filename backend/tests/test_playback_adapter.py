"""Verify the display adapter's measured geometry, not merely its encoded schema."""
import unittest
import numpy as np
import trimesh
from skellyclicker_app.playback_adapter import convert_geometry,camera_to_world,build_project_playback
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
 def test_cancel_before_any_files_are_touched(self):
  with self.assertRaises(InterruptedError):build_project_playback(Path('this-does-not-exist.json'),cancelled=lambda:True)

if __name__=='__main__':unittest.main()
