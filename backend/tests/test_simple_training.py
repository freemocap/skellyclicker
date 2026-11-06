import importlib.util,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from skellyclicker_app.training_routes import TrainingRequest
from skellyclicker_app.training_checkpoints import recommend
spec=importlib.util.spec_from_file_location('worker',Path(__file__).parents[1]/'skellyclicker_app/workers/train_dlc.py');worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
class SimpleTrainingTest(unittest.TestCase):
 def test_default_and_persisted_controls(self):
  request=TrainingRequest(project_path='fixture');self.assertFalse(request.pose_validation);self.assertEqual(request.checkpoint_metric,'mean_px')
  self.assertEqual(TrainingRequest.model_validate_json(request.model_dump_json()),request)
  with self.assertRaises(ValueError):TrainingRequest(project_path='fixture',checkpoint_metric='pose')
 def test_pixel_definition_and_missing_denominator(self):
  result=worker.keypoint_measurement([[3,4,.1],[float('nan'),2,.99],[8,8,1]],[[0,0],[1,2],[8,8]],[True,True,False])
  self.assertEqual(result,{'expected_points':2,'predicted_points':1,'missing_points':1,'distances_px':[5.]})
 def test_missing_predictions_cannot_win_and_metric_changes_choice(self):
  rows=[{'path':str(i),'epoch':i,'validation_mean_px':m,'validation_p95_px':p,'keypoint_validation':{'missing_points':missing,'expected_points':10,'predicted_points':10-missing}} for i,m,p,missing in [(1,2,8,0),(2,3,6,0),(3,.1,.2,1)]]
  self.assertEqual(recommend(rows,'mean_px')[0]['epoch'],1);self.assertEqual(recommend(rows,'p95_px')[0]['epoch'],2)
  self.assertIsNone(recommend([rows[-1]],'mean_px')[0])
if __name__=='__main__':unittest.main()
