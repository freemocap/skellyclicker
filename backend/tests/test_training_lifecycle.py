import json,sys,threading,time,unittest
from unittest.mock import patch
import test_labels
from skellyclicker_app.training_routes import TrainingRequest,start,inspect_run,artifact
from skellyclicker_app.training_inputs import training_input_preview
from skellyclicker_app.job_lifecycle import jobs
from skellyclicker_app.label_routes import registry
from freemocap_sdk.storage import atomic_json,file_digest
from fastapi import HTTPException

class TrainingLifecycleTest(unittest.TestCase):
 setUp=test_labels.LabelsTest.setUp
 tearDown=test_labels.LabelsTest.tearDown
 generate=test_labels.LabelsTest.generate
 run_job=test_labels.LabelsTest.run_job
 def training_request(self):
  self.request=self.request.model_copy(update={'step':1});self.run_job()
  request=TrainingRequest(project_path=str(self.manifest),python_path=sys.executable,guard_seconds=0,epochs=2)
  preview=training_input_preview(request)
  return request.model_copy(update={k:preview[k] for k in ('expected_selection_sha256','expected_label_manifest_sha256')})
 def test_retained_completed_run_and_confined_artifacts(self):
  request=self.training_request()
  def worker(mode,job,ctx):
   if mode=='prepare':atomic_json(job['work']/'prepared.json',{'test_fixture':True})
   else:
    ctx.metric('loss',label='Fixture test loss',step=1,value=.25,unit='loss')
    (job['work']/'events.jsonl').write_text('')
    (job['work']/'checkpoint.pt').write_bytes(b'test checkpoint')
    atomic_json(job['work']/'trained.json',{'checkpoint':'checkpoint.pt','checkpoint_sha256':file_digest(job['work']/'checkpoint.pt')})
  with patch('skellyclicker_app.training_pipeline.run_worker',side_effect=worker):
   response=start(request);run=response['run_id'];jobs[run]['thread'].join(10)
  self.assertEqual(inspect_run(run,str(self.manifest))['status'],'complete')
  self.assertTrue((jobs[run]['work']/'result.json').is_file())
  live=jobs.pop(run)
  try:self.assertEqual(inspect_run(run,str(self.manifest))['metrics'][0]['points'][0]['value'],.25)
  finally:jobs[run]=live
  with self.assertRaises((HTTPException,ValueError)):artifact(run,str(self.manifest),'../../other')
 def test_cancellation_and_single_job_admission(self):
  request=self.training_request();entered=threading.Event()
  def worker(mode,job,ctx):
   entered.set()
   while True:ctx.check_cancelled();time.sleep(.01)
  with patch('skellyclicker_app.training_pipeline.run_worker',side_effect=worker):
   response=start(request);run=response['run_id'];self.assertTrue(entered.wait(5))
   with self.assertRaises(HTTPException) as e:start(request)
   self.assertEqual(e.exception.status_code,409)
   registry.get(run).cancel();jobs[run]['thread'].join(5)
  self.assertEqual(inspect_run(run,str(self.manifest))['status'],'cancelled')
  self.assertFalse((jobs[run]['work']/'result.json').exists())
