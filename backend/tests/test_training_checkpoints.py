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

if __name__=='__main__':unittest.main()
