import json,unittest
from uuid import uuid4
from pathlib import Path
import test_labels
from freemocap_sdk.storage import atomic_json,file_digest
from skellyclicker_app.training_routes import TrainingRequest
from skellyclicker_app.training_inputs import freeze_training_inputs,training_input_preview
from skellyclicker_app.training_checkpoints import checkpoints,bind_parent

class CheckpointsTest(unittest.TestCase):
 setUp=test_labels.LabelsTest.setUp
 tearDown=test_labels.LabelsTest.tearDown
 generate=test_labels.LabelsTest.generate
 run_job=test_labels.LabelsTest.run_job
 def test_recommend_verify_and_preserve_split(self):
  self.request=self.request.model_copy(update={'step':1});self.run_job()
  request=TrainingRequest(project_path=str(self.manifest),guard_seconds=0)
  snapshot=freeze_training_inputs(request);run_id=str(uuid4())
  folder=self.root/'recordings/capture/skellyclicker/training-runs'/run_id
  (folder/'checkpoints').mkdir(parents=True);atomic_json(folder/'dataset.json',snapshot)
  events=[]
  for epoch,error in [(1,2.0),(2,3.0)]:
   relative=f'checkpoints/epoch-{epoch:06d}.pt';path=folder/relative;path.write_bytes(f'fixture{epoch}'.encode())
   events.extend([{'kind':'metric','id':'validation_mean_px','step':epoch,'value':error},{'kind':'checkpoint','epoch':epoch,'path':relative,'sha256':file_digest(path)}])
  (folder/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events)+'{')
  listed=checkpoints(str(self.manifest),run_id);self.assertEqual(len(listed['checkpoints']),2);self.assertEqual(listed['recommended_path'],'checkpoints/epoch-000001.pt')
  selected=listed['checkpoints'][0];continued=request.model_copy(update={'parent_run_id':run_id,'parent_checkpoint':selected['path'],'parent_checkpoint_sha256':selected['sha256'],'validation_fraction':.49})
  preview=training_input_preview(continued)
  self.assertEqual(preview['validation_start_ns'],snapshot['manifest']['validation_start_ns'])
  self.assertEqual(preview['counts'],snapshot['manifest']['counts'])
  self.assertEqual(preview['parent_checkpoint']['epoch'],1)
  changed={**snapshot['manifest'],'stl_sha256':'0'*64}
  with self.assertRaises(ValueError):bind_parent(continued,changed)
  (folder/selected['path']).write_bytes(b'corrupted')
  with self.assertRaises(ValueError):training_input_preview(continued)

class RecommendationTest(unittest.TestCase):
 def test_pose_metrics_can_override_best_keypoints_and_failure_has_priority(self):
  from skellyclicker_app.training_checkpoints import recommend
  def row(epoch,kp,position,orientation,failure=0):
   return {'path':str(epoch),'epoch':epoch,'validation_mean_px':kp,'pose_validation':{'reference_images':8,'validation_images':10,'metrics':{'validation_position_mm':position,'validation_orientation_deg':orientation,'validation_pose_failure_pct':failure}}}
  values=[row(1,1,20,30),row(2,2,2,3),row(3,.1,.1,.1,25)]
  best,reason=recommend(values);self.assertEqual(best['epoch'],2)
  self.assertIn('8/10',reason);self.assertIn('equally weighted',reason);self.assertIn('0.0% pose failures',reason)
 def test_old_runs_and_all_failed_are_explicit(self):
  from skellyclicker_app.training_checkpoints import recommend
  best,reason=recommend([{'path':'a','epoch':1,'validation_mean_px':2,'pose_validation':{'reference_images':8,'metrics':{'validation_pose_failure_pct':100}}}])
  self.assertIn('Pose-based comparison is unavailable',reason)

if __name__=='__main__':unittest.main()
