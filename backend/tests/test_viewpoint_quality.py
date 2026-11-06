import unittest,math,tempfile
from pathlib import Path
import numpy as np
import trimesh
from freemocap_sdk.storage import file_digest
from skellyclicker_app.viewpoint_quality import viewing_direction,spherical_bin,coverage_pool,select_viewpoints,mesh_frame
from skellyclicker_app.quality_routes import QualityRequest
class ViewpointTest(unittest.TestCase):
 def test_inverse_translation_center_and_stereo(self):
  T=np.eye(4);T[:3,3]=[0,0,2]
  np.testing.assert_allclose(viewing_direction(T,[0,0,0]),[0,0,-1])
  right=T.copy();right[0,3]=-.1
  self.assertGreater(viewing_direction(right,[0,0,0])[0],0)
  np.testing.assert_allclose(viewing_direction(T,[1,0,0]),np.array([-1,0,-2])/math.sqrt(5))
 def test_rotation_front_back_and_invalid(self):
  T=np.diag([-1,1,-1,1]);T[:3,3]=[0,0,2]
  np.testing.assert_allclose(viewing_direction(T,[0,0,0]),[0,0,1])
  self.assertIsNone(viewing_direction(np.eye(4),[0,0,0]))
  T[0,0]=2;self.assertIsNone(viewing_direction(T,[0,0,0]))
  self.assertIsNone(viewing_direction(None,[0,0,0]))
 def test_common_world_rigid_transform_invariance(self):
  object_world=np.eye(4);object_world[:3,3]=[1,2,3]
  camera_world=np.eye(4);camera_world[:3,3]=[-2,4,6]
  G=np.array([[0,-1,0,4],[1,0,0,7],[0,0,1,-2],[0,0,0,1.]])
  relative=np.linalg.inv(camera_world)@object_world
  changed=np.linalg.inv(G@camera_world)@(G@object_world)
  np.testing.assert_allclose(viewing_direction(relative,[.01,.02,0]),viewing_direction(changed,[.01,.02,0]))
 def test_mesh_units_and_off_origin_center(self):
  with tempfile.TemporaryDirectory() as tmp:
   for units,scale in [('mm',1000),('m',1)]:
    mesh=trimesh.creation.box(extents=np.array([.1,.2,.3])*scale);mesh.apply_translation(np.array([1,2,3])*scale);path=Path(tmp)/(units+'.stl');mesh.export(path)
    center,radius,factor=mesh_frame(path,file_digest(path),path.stat().st_size,path.stat().st_mtime_ns,units)
    np.testing.assert_allclose(center,[1,2,3],atol=1e-6);self.assertAlmostEqual(radius,math.sqrt(.14)/2*1.3,places=5)
 def test_equal_area_cells_poles_and_conservation(self):
  az,z=12,6
  bins=[]
  for zi in range(z):
   for pi in range(az):
    height=-1+(zi+.5)*2/z;phi=(pi+.5)*2*math.pi/az;r=math.sqrt(1-height*height)
    bins.append(spherical_bin([r*math.cos(phi),r*math.sin(phi),height],az,z))
  self.assertEqual(bins,list(range(72)));self.assertEqual(spherical_bin([0,0,1],az,z),60);self.assertEqual(spherical_bin([0,0,-1],az,z),0)
  rows=[{'image_id':str(i),'viewpoint':{'direction':[1,0,0],'bin':b}} for i,b in enumerate(bins)]+[{'image_id':'unknown','viewpoint':None}]
  pool=coverage_pool(rows,az,z);self.assertEqual(sum(pool['counts'])+pool['unknown_count'],73)
 def test_diversity_before_quality_and_determinism(self):
  rows=[dict(image_id=str(i),score=100-i,source_frame=i,camera_id='left',timestamp_ns=str(i*10**9),eligible=True,viewpoint={'bin':0 if i<5 else i-4,'direction':[1,0,0]}) for i in range(8)]
  q=QualityRequest(project_path='p',expected_label_manifest_sha256='l',expected_selection_sha256='s',top_n=4)
  self.assertEqual(select_viewpoints(rows,q),['0','5','6','7']);self.assertEqual(select_viewpoints(rows[::-1],q),['0','5','6','7'])
  self.assertEqual(select_viewpoints(rows,q.model_copy(update={'selection_mode':'quality_only'})),['0','1','2','3'])
  self.assertEqual(len(select_viewpoints(rows,q.model_copy(update={'top_n':100,'spacing_seconds':3}))),2)
