import unittest
from skellyclicker_app.target_crops import projection_bounds

class TargetCropTests(unittest.TestCase):
 def test_padding_and_edge_clamp(self):
  value=projection_bounds({'positive_depth':True,'keypoints_xy':[[2,5],[20,30]],'mesh_wireframe_segments_xy':[[[1,2],[25,32]]]},100,80)
  self.assertEqual(value,dict(x=0.,y=0.,width=28.,height=35.))
 def test_unavailable_does_not_show_unrelated_pixels(self):
  for value in (None,{'positive_depth':False,'keypoints_xy':[[2,3]]},{'positive_depth':True,'keypoints_xy':[[-30,5],[-1,30]]},{'positive_depth':True,'keypoints_xy':[[float('nan'),2]]}):
   self.assertIsNone(projection_bounds(value,100,80))

 def test_thumbnail_preserves_outline_and_keypoints_without_letterbox(self):
  import tempfile,json
  from io import BytesIO
  from pathlib import Path
  from PIL import Image
  from freemocap_sdk.storage import file_digest
  from skellyclicker_app.label_routes import image_thumbnail
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);source=root/'source.png';Image.new('RGB',(120,80),'white').save(source)
   projection=root/'projection.jsonl';projection.write_text(json.dumps({'projection':{'mesh_wireframe_segments_xy':[[[10,10],[80,10]]]}})+'\n')
   data=image_thumbnail(source,file_digest(source),source.stat().st_size,source.stat().st_mtime_ns,(0,0,100,60),((40,40,True),),projection,0,file_digest(projection))
   output=Image.open(BytesIO(data));self.assertEqual(output.size,(100,60));self.assertEqual(output.format,'PNG')
   self.assertEqual(output.getpixel((40,10)),(55,234,255));self.assertEqual(output.getpixel((40,40)),(255,69,230));self.assertEqual(output.getpixel((0,0)),(255,255,255))
