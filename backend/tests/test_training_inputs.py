import json
from pathlib import Path
import pyarrow.parquet as pq
import unittest
import test_labels
from skellyclicker_app.label_routes import selection_view,save_selection,SelectMoment,run_result
from skellyclicker_app.training_inputs import TrainingInputs,training_input_preview,freeze_training_inputs
from skellyclicker_app.label_inputs import StaleInputs
from skellyclicker_app.projects import read_model,Project
from freemocap_sdk.storage import file_digest

class TrainingInputsTest(unittest.TestCase):
 setUp=test_labels.LabelsTest.setUp
 tearDown=test_labels.LabelsTest.tearDown
 generate=test_labels.LabelsTest.generate
 run_job=test_labels.LabelsTest.run_job
 def test_frozen_snapshot_preserves_approval_identity_and_independence(self):
  self.request=self.request.model_copy(update={'step':1});run=self.run_job();result=run_result(run)['result']
  selection=selection_view(self.manifest);self.assertEqual(selection['review_state'],'proposed')
  request=TrainingInputs(project_path=str(self.manifest),guard_seconds=.02,expected_selection_sha256=selection['sha256'])
  preview=training_input_preview(request);self.assertEqual(preview['counts'],{'training':6,'validation':2,'guard':0})
  before=self.manifest.read_bytes();snapshot=freeze_training_inputs(request);folder=self.root/snapshot['path']
  self.assertEqual(self.manifest.read_bytes(),before)
  rows=pq.read_table(folder/'images.parquet').to_pylist();self.assertEqual(rows[0]['timestamp_ns'],1000000000333333330)
  self.assertEqual(snapshot['manifest']['review_state'],'approved');self.assertEqual(snapshot['manifest']['label_origin'],'pose_projection')
  for moment in {r['moment_id'] for r in rows}:self.assertEqual(len({r['split'] for r in rows if r['moment_id']==moment}),1)
  for name,identity in snapshot['manifest']['files'].items():self.assertEqual(file_digest(folder/name),identity['sha256'])
  image=result['images'][0]
  revised=save_selection(SelectMoment(project_path=str(self.manifest),expected_label_manifest_sha256=result['manifest_sha256'],expected_selection_sha256=selection['sha256'],moment_id=image['moment_id'],source_frame=image['source_frame'],timestamp_ns=image['timestamp_ns'],camera_id=image['camera_id'],selected=False))
  self.assertEqual(revised['review_state'],'approved');self.assertEqual(len(pq.read_table(folder/'images.parquet')),8)
  with self.assertRaises(StaleInputs):freeze_training_inputs(request)
  (self.result/'frames/000010-left.png').write_bytes(b'changed original')
  self.assertEqual(file_digest(folder/rows[0]['path']),rows[0]['sha256'])

 def test_timestamp_guard_retains_all_included_images(self):
  self.request=self.request.model_copy(update={'step':1});self.run_job()
  p=training_input_preview(TrainingInputs(project_path=str(self.manifest),guard_seconds=.05))
  self.assertEqual(p['counts'],{'training':4,'validation':2,'guard':2});self.assertEqual(p['image_count'],8)
  times={role:[int(r['timestamp_ns']) for r in p['images'] if r['split']==role] for role in p['counts']}
  self.assertGreater(min(times['validation'])-max(times['training']),50_000_000)
  with self.assertRaises(ValueError):training_input_preview(TrainingInputs(project_path=str(self.manifest),guard_seconds=60))

 def test_changed_source_cannot_publish(self):
  self.request=self.request.model_copy(update={'step':1});self.run_job()
  (self.result/'frames/000010-left.png').write_bytes(b'changed')
  with self.assertRaises(ValueError):freeze_training_inputs(TrainingInputs(project_path=str(self.manifest),guard_seconds=0))
  self.assertFalse((self.root/'recordings/capture/skellyclicker/training-inputs').exists())
