import json,tempfile,unittest
from pathlib import Path
import numpy as np,trimesh
from freemocap_sdk.storage import atomic_json
from skellyclicker_app.projects import Target,Artifact,artifact
from skellyclicker_app.authored_geometry import load_authored_geometry
from skellyclicker_app.playback_adapter import convert_geometry

class AuthoredGeometryTest(unittest.TestCase):
 def test_order_topology_frame_and_hash_guard(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);sha='a'*64
   points=np.array([[12,3,8],[9,7,14],[-3,4,6],[1,-2,5]],dtype=float)
   data={'units':'mm','source_stl_sha256':sha,'points':[{'group':'shell','name':str(i),'xyz_mm':v.tolist()} for i,v in enumerate(points)],'connections':[{'ids':[2,0,3,1],'closed':True}]}
   atomic_json(root/'points.json',data);(root/'outline.bin').write_bytes(b'fixture')
   def ref(name):return artifact(root/name,name).model_dump()
   atomic_json(root/'authoring.json',{'source_stl_sha256':sha,'keypoints':ref('points.json'),'outline':ref('outline.bin'),'origin_mm':[4,5,6]})
   target=Target(object_id='arbitrary',source_path='mesh.stl',geometry=Artifact(path='mesh.stl',sha256=sha,bytes=0),authored_units='m',authored_geometry=artifact(root/'authoring.json','authoring.json'))
   authored=load_authored_geometry(root,target);self.assertEqual(authored['names'],tuple('shell / '+str(i) for i in range(4)))
   np.testing.assert_array_equal(authored['edges'],[[2,0],[0,3],[3,1],[1,2]])
   mesh=trimesh.creation.box(extents=[.07,.03,.045]);rigid,source,local,*_=convert_geometry(mesh,target,authored)
   np.testing.assert_allclose(source,points/1000)
   np.testing.assert_allclose(trimesh.transform_points(local,rigid.segment_reference_to_source_mesh),source,atol=1e-12)
   (root/'points.json').write_text('{}')
   with self.assertRaisesRegex(ValueError,'Changed authored'):load_authored_geometry(root,target)

if __name__=='__main__':unittest.main()
