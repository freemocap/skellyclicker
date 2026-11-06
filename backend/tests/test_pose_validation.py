import importlib.util,unittest
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('worker',Path(__file__).parents[1]/'skellyclicker_app/workers/train_dlc.py')
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)

@unittest.skipUnless(importlib.util.find_spec('cv2'), 'Run these worker tests with the isolated DLC Python (OpenCV is not a backend dependency)')
class PoseValidationTest(unittest.TestCase):
 def setUp(self):
  import cv2
  self.cv=cv2;self.points=np.random.default_rng(8).uniform(-30,30,(30,3))
  self.K=np.array([[600.,0,640],[0,600,360],[0,0,1]])
  self.R=cv2.Rodrigues(np.array([.2,-.3,.1]))[0];self.t=np.array([25.,-12.,600.])
  T=np.eye(4);T[:3,:3]=self.R;T[:3,3]=self.t/1000
  self.ref={'accepted':True,'T_camera_from_stl_m':T.tolist()}
 def prediction(self,R=None,t=None):
  xy=self.cv.projectPoints(self.points,self.cv.Rodrigues(self.R if R is None else R)[0],self.t if t is None else t,self.K,None)[0].reshape(-1,2)
  return np.column_stack([xy,np.ones(len(xy))])
 def test_exact_pose_and_known_translation_rotation(self):
  value=worker.evaluate_pose(self.prediction(),self.points,self.K,self.ref)
  self.assertEqual(value['status'],'ok');self.assertLess(value['position_mm'],.01);self.assertLess(value['orientation_deg'],.01)
  rotated=self.cv.Rodrigues(np.array([0.,0.,np.pi/6]))[0]@self.R
  value=worker.evaluate_pose(self.prediction(rotated,self.t+[3,4,0]),self.points,self.K,self.ref)
  self.assertAlmostEqual(value['position_mm'],5,places=2);self.assertAlmostEqual(value['orientation_deg'],30,places=2)
 def test_outliers_and_missing_predictions(self):
  pred=self.prediction();pred[:5,:2]+=[200,-150]
  value=worker.evaluate_pose(pred,self.points,self.K,self.ref);self.assertEqual(value['status'],'ok');self.assertLess(value['position_mm'],.1)
  pred[:,2]=0;self.assertEqual(worker.evaluate_pose(pred,self.points,self.K,self.ref)['status'],'failed')
  pred[:]=np.nan;self.assertEqual(worker.evaluate_pose(pred,self.points,self.K,self.ref)['status'],'failed')
 def test_reference_coverage_and_failure_denominator(self):
  ok=worker.evaluate_pose(self.prediction(),self.points,self.K,self.ref)
  missing=worker.evaluate_pose(self.prediction(),self.points,self.K,None)
  summary=worker.summarize_poses([ok,{'status':'failed'},missing])
  self.assertEqual(summary['reference_images'],2);self.assertEqual(summary['reference_unavailable'],1)
  self.assertEqual(summary['metrics']['validation_pose_failure_pct'],50)
  self.assertNotIn('validation_position_mm',worker.summarize_poses([{'status':'failed'}])['metrics'])
 def test_reference_never_initializes_solver(self):
  changed={**self.ref,'T_camera_from_stl_m':np.eye(4).tolist()}
  a=worker.evaluate_pose(self.prediction(),self.points,self.K,self.ref)
  b=worker.evaluate_pose(self.prediction(),self.points,self.K,changed)
  np.testing.assert_allclose(a['T_camera_from_stl_m'],b['T_camera_from_stl_m'])
 def test_degenerate_points_fail(self):
  points=np.zeros((30,3));points[:,0]=np.arange(30)
  self.assertEqual(worker.evaluate_pose(self.prediction(),points,self.K,self.ref)['status'],'failed')

if __name__=='__main__':unittest.main()
