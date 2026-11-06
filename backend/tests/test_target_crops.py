import unittest
from skellyclicker_app.target_crops import projection_bounds

class TargetCropTests(unittest.TestCase):
 def test_padding_and_edge_clamp(self):
  value=projection_bounds({'positive_depth':True,'keypoints_xy':[[2,5],[20,30]],'mesh_wireframe_segments_xy':[[[1,2],[25,32]]]},100,80)
  self.assertEqual(value,dict(x=0.,y=0.,width=41.,height=48.))
 def test_unavailable_does_not_show_unrelated_pixels(self):
  for value in (None,{'positive_depth':False,'keypoints_xy':[[2,3]]},{'positive_depth':True,'keypoints_xy':[[-30,5],[-1,30]]},{'positive_depth':True,'keypoints_xy':[[float('nan'),2]]}):
   self.assertIsNone(projection_bounds(value,100,80))
