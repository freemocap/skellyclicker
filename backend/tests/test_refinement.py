import importlib.util,unittest
from pathlib import Path
import test_labels
from skellyclicker_app.label_routes import run_result,selection_view
from skellyclicker_app.label_inputs import PreviewLabels,preview
spec=importlib.util.spec_from_file_location('worker',Path(__file__).parents[1]/'skellyclicker_app/workers/train_dlc.py');worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)

class RankingTest(unittest.TestCase):
 def test_balance_backfill_and_temporal_diversity(self):
  rows=[{'group':group,'source_frame':i,'camera_id':'left','timestamp_ns':str(i*1_000_000_000),'score':20-i} for group,values in [('near_miss',[0,1,2,8]),('major_failure',[3,4,5,9])] for i in values]
  selected=worker.select_refinement_examples(rows,4,2_000_000_000)
  self.assertEqual(len(selected),4);self.assertEqual(sum(r['group']=='near_miss' for r in selected),2)
  self.assertTrue(all(abs(int(a['timestamp_ns'])-int(b['timestamp_ns']))>=2_000_000_000 for i,a in enumerate(selected) for b in selected[i+1:]))
  self.assertEqual(len(worker.select_refinement_examples([r for r in rows if r['group']=='near_miss'],10,0)),4)

class ExactAdditionTest(unittest.TestCase):
 setUp=test_labels.LabelsTest.setUp
 tearDown=test_labels.LabelsTest.tearDown
 generate=test_labels.LabelsTest.generate
 run_job=test_labels.LabelsTest.run_job
 def test_reviewed_camera_images_only_are_added(self):
  self.run_job();old=set(selection_view(self.manifest)['selected_image_ids'])
  self.request=PreviewLabels(project_path=str(self.manifest),start_frame=11,end_frame=13,image_keys=['11:left','13:right'])
  self.assertEqual(preview(self.request)['image_count'],2)
  result=run_result(self.run_job())['result'];selected=selection_view(self.manifest)['selected_image_ids']
  self.assertEqual(len(selected),len(old)+2)
  added=[r for r in result['images'] if r['image_id'] not in old]
  self.assertEqual({(r['source_frame'],r['camera_id']) for r in added},{(11,'left'),(13,'right')})

class RefinementIntegrationTest(ExactAdditionTest):
 def test_analysis_review_accept_does_not_mutate_dataset_until_accept(self):
  import json,sys
  from uuid import uuid4
  from unittest.mock import patch
  from freemocap_sdk.storage import atomic_json,file_digest
  from skellyclicker_app.projects import recording_structure
  from skellyclicker_app.training_routes import TrainingRequest
  from skellyclicker_app.training_inputs import freeze_training_inputs
  from skellyclicker_app.refinement_routes import MineRequest,start,inspect,accept,Accept
  from skellyclicker_app.job_lifecycle import jobs
  self.request=self.request.model_copy(update={'image_keys':['10:left','10:right','12:left','12:right','13:left','13:right']});self.run_job()
  parent=freeze_training_inputs(TrainingRequest(project_path=str(self.manifest),guard_seconds=0))
  paths=recording_structure(self.root,'capture');rid=str(uuid4());parent_folder=paths.application_dir('skellyclicker')/'training-runs'/rid
  (parent_folder/'checkpoints').mkdir(parents=True);cp=parent_folder/'checkpoints/epoch-000001.pt';cp.write_bytes(b'checkpoint fixture')
  atomic_json(parent_folder/'dataset.json',parent);atomic_json(parent_folder/'prepared.json',{'pose':'fixture.yaml'})
  (parent_folder/'events.jsonl').write_text(json.dumps({'kind':'checkpoint','epoch':1,'path':'checkpoints/epoch-000001.pt','sha256':file_digest(cp)})+'\n')
  atomic_json(self.result/'summary.json',{'frames':[{'source_frame':i} for i in range(10,14)]})
  paths.source_timing_path.parent.mkdir(exist_ok=True,parents=True);atomic_json(paths.source_timing_path,{'source_frame_indices':[10,11,12,13],'timestamps_ns':[1000000000000000000+i*33333333 for i in range(10,14)]})
  paths.videos_synchronized_dir.mkdir(exist_ok=True,parents=True)
  for camera in ('left','right'):(paths.videos_synchronized_dir/(camera+'.mp4')).write_bytes(b'video fixture')
  from skellyclicker_app.projects import read_model,Project,Recording
  project=read_model(self.manifest,Project);recording=read_model(self.root/project.recording_manifests[0],Recording)
  info={'videos':{'left':'left.mp4','right':'right.mp4'},'input_provenance':{'source_sha256':recording.source.sha256}}
  before=self.manifest.read_bytes();old=set(selection_view(self.manifest)['selected_image_ids'])
  def worker(mode,job,ctx):
   self.assertEqual(mode,'mine');request=json.loads((job['work']/'worker-request.json').read_text());self.assertEqual(request['source_frames'],[10,11,12,13]);self.assertEqual(len(request['reviewed_keys']),6)
   atomic_json(job['work']/'result.json',{'counts':{'scanned':8},'proposals':[{'key':'11:left','source_frame':11,'camera_id':'left','group':'near_miss'}]});(job['work']/'predictions.jsonl').write_text('')
  request=MineRequest(project_path=str(self.manifest),python_path=sys.executable,parent_run_id=rid,parent_checkpoint='checkpoints/epoch-000001.pt',parent_checkpoint_sha256=file_digest(cp))
  with patch('skellyclicker_app.recording_layout.verify_recording_inputs',return_value=info),patch('skellyclicker_app.refinement_routes.projection_source',return_value=self.cache),patch('skellyclicker_app.refinement_routes.run_worker',side_effect=worker):
   run=start(request)['run_id'];jobs[run]['thread'].join(10)
  self.assertEqual(inspect(run,str(self.manifest))['snapshot']['status'],'complete')
  self.assertEqual(self.manifest.read_bytes(),before)
  with patch('skellyclicker_app.label_pipeline.projection_source',return_value=self.cache):
   accepted=accept(run,Accept(project_path=str(self.manifest),image_keys=['11:left']));jobs[accepted['run_id']]['thread'].join(10)
  self.assertEqual(len(selection_view(self.manifest)['selected_image_ids']),len(old)+1)
  self.assertTrue(old<=set(selection_view(self.manifest)['selected_image_ids']))
  self.assertEqual(inspect(run,str(self.manifest))['accepted']['snapshot']['status'],'complete')
  self.assertEqual(accept(run,Accept(project_path=str(self.manifest),image_keys=['11:left']))['run_id'],accepted['run_id'])
