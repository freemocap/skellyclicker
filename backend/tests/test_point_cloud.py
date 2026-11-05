import unittest
import numpy as np
from skellyclicker_app.point_cloud import project_depth
from skellyclicker_app.playback_adapter import camera_to_world

class PointCloudTest(unittest.TestCase):
 def test_depth_color_and_world_projection(self):
  depth=np.array([[1.,np.nan],[.1,2.]],dtype=np.float32)
  rgb=np.array([[[1,2,3],[4,5,6]],[[7,8,9],[10,11,12]]],dtype=np.uint8)
  points,colors=project_depth(depth,rgb,[[2,0,0],[0,4,0],[0,0,1]],camera_to_world(),stride=1)
  np.testing.assert_allclose(points,[[0,1000,0],[1000,2000,-500]])
  np.testing.assert_array_equal(colors,[[1,2,3],[10,11,12]])
  self.assertEqual(points.dtype,np.dtype('<f4'))
  self.assertTrue(points.flags.c_contiguous)

 def test_chunk_offsets_identity_and_bounded_sampling(self):
  import json,struct,tempfile
  from pathlib import Path
  from skellyclicker_app.point_cloud import write_display_clouds
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);source=root/'source';source.mkdir();frames=[]
   positions=np.arange(90000,dtype='<f4').reshape(-1,3);colors=np.full((30000,3),127,dtype=np.uint8)
   origin=1793852540236213001
   for i in range(16):
    name=str(i)+'.npz';np.savez(source/name,positions=positions,colors=colors)
    frames.append({'path':name,'source_frame':90+i,'timestamp_ns':origin+i*33333333})
   (source/'manifest.json').write_text(json.dumps({'frames':frames,'source':'fixture','source_sha256':'test','sampling':{}}))
   ref={'id':'blender_world','definition':{'name':'blender_world','basis':'blender_x_right_y_forward_z_up','units':'mm','alignment':None,'additional_transform':None}}
   manifest=write_display_clouds(source,root/'display',revision='test',reference_frame=ref)
   self.assertEqual(len(manifest['chunks']),2)
   self.assertEqual(manifest['frames'][15]['chunk_index'],1)
   for index,chunk in enumerate(manifest['chunks']):
    data=(root/'display'/chunk['url']).read_bytes();length=struct.unpack_from('<I',data)[0]
    header=json.loads(data[4:4+length]);start=(4+length+3)&~3
    self.assertEqual(header['reference_frame'],ref)
    self.assertLess(len(data),8*1024*1024)
    for frame in header['frames']:
     self.assertEqual(frame['point_count'],25000)
     self.assertEqual(frame['positions_offset']%4,0)
     self.assertEqual(frame['source_frame_index'],frame['frame_index']+90)
     self.assertEqual(int(frame['timestamp_ns']),origin+frame['frame_index']*33333333)
     actual=np.frombuffer(data,dtype='<f4',count=frame['point_count']*3,offset=start+frame['positions_offset']).reshape(-1,3)
     np.testing.assert_array_equal(actual[[0,-1]],positions[[0,-1]])
     actual_colors=np.frombuffer(data,dtype=np.uint8,count=frame['point_count']*3,offset=start+frame['colors_offset'])
     self.assertTrue((actual_colors==127).all())
