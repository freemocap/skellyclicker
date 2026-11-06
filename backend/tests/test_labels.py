import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import trimesh
from fastapi import HTTPException
from freemocap_sdk.storage import atomic_json,inventory
from skellyclicker_app.projects import CreateProject,create_project,read_model,Project,Target,artifact
from skellyclicker_app.label_inputs import PreviewLabels,GenerateLabels,preview
from skellyclicker_app.label_routes import start_labels,run_result,registry,save_selection,SelectMoment,selection_view
from skellyclicker_app.job_lifecycle import jobs


class LabelsTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();base=Path(self.temp.name);capture=base/'capture';capture.mkdir()
  (capture/'stereo.svo2').write_bytes(b'source');(capture/'cal.conf').write_bytes(b'cal')
  stl=base/'part.stl';stl.write_bytes(trimesh.creation.box().export(file_type='stl'))
  view=create_project(CreateProject(project_path=str(base/'project'),source_svo=str(capture/'stereo.svo2'),calibration_source=str(capture/'cal.conf'),source_stl=str(stl)))
  self.manifest=Path(view['manifest_path']);self.root=self.manifest.parent;p=read_model(self.manifest,Project);tp=self.root/p.target_manifests[0];target=read_model(tp,Target)
  points={'units':'mm','source_stl_sha256':target.geometry.sha256,'points':[{'group':'g','name':str(i),'xyz_mm':xyz} for i,xyz in enumerate([[0,0,0],[1,0,0],[0,1,0]])],'connections':[{'ids':[0,1,2],'closed':True}]}
  atomic_json(tp.parent/'keypoints.json',points);(tp.parent/'outline.bin').write_bytes(b'outline')
  spec={'path_basis':'target_directory','source_stl_sha256':target.geometry.sha256,'origin_mm':[0,0,0],**{name:artifact(tp.parent/file,file).model_dump() for name,file in [('keypoints','keypoints.json'),('outline','outline.bin')]}}
  atomic_json(tp.parent/'authored_geometry.json',spec);target.authored_geometry=artifact(tp.parent/'authored_geometry.json','authored_geometry.json');atomic_json(tp,target.model_dump())
  self.result=self.root/'recordings/capture/skellyclicker/results/fixture/r001';self.result.mkdir(parents=True)
  rows=[{'source_frame':f,'timestamp_ns':1000000000000000000+f*33333333,'accepted':f%2==0,'status':'accepted' if f%2==0 else 'rejected'} for f in range(10,14)]
  pq.write_table(pa.Table.from_pylist(rows),self.result/'candidates.parquet');pq.write_table(pa.Table.from_pylist([{k:r[k] for k in ('source_frame','timestamp_ns')} for r in rows]),self.result/'timing.parquet')
  cal={'image_width':100,'image_height':80};atomic_json(self.result/'calibration.json',cal)
  frames=self.result/'frames';frames.mkdir()
  for row in rows:
   for camera in ('left','right'):(frames/f'{row["source_frame"]:06d}-{camera}.png').write_bytes(b'raw image fixture')
  descriptor={'recording_id':'capture','source_sha256':view['recordings'][0]['source']['sha256'],'target_sha256':target.geometry.sha256,'geometry':{'source_units':'mm'},'calibration':cal}
  atomic_json(self.result/'manifest.json',{'descriptor':descriptor,'files':{k:v.model_dump() for k,v in inventory(self.result).items()}})
  p.sample_result=self.result.relative_to(self.root).as_posix();atomic_json(self.manifest,p.model_dump())
  self.cache=base/'projections.jsonl'
  self.cache.write_text(''.join(json.dumps({'source_frame':r['source_frame'],'camera':c,'projection':{'keypoints_xy':[[1,2],[3,4],[110,9]],'visibility':[True,False,True],'positive_depth':True}})+'\n' for r in rows for c in ('left','right')))
  self.request=PreviewLabels(project_path=str(self.manifest),start_frame=10,end_frame=13,step=2)
 def tearDown(self):self.temp.cleanup()
 def generate(self):
  p=preview(self.request)
  return GenerateLabels(**self.request.model_dump(),**{k:p[k] for k in ('expected_pose_manifest_sha256','expected_target_manifest_sha256')})
 def run_job(self,request=None):
  with patch('skellyclicker_app.label_pipeline.projection_source',return_value=self.cache):
   started=start_labels(request or self.generate());jobs[started['run_id']]['thread'].join(10)
  self.assertFalse(jobs[started['run_id']]['thread'].is_alive());return started['run_id']
 def test_preview_run_selection_and_retained_two_runs(self):
  before=self.manifest.read_bytes();self.assertEqual(preview(self.request)['label_count'],12);self.assertEqual(before,self.manifest.read_bytes())
  first=self.run_job();view=run_result(first);self.assertEqual(view['status'],'complete',registry.get(first).snapshot())
  result=view['result'];self.assertEqual(result['manifest']['label_count'],12)
  labels=pq.read_table(self.root/result['path']/'labels.parquet');self.assertEqual(labels.schema.field('invalid_reason').type,pa.string());self.assertIn('recipe_bytecode_sha256',result['manifest']);self.assertEqual(labels.column('external_occlusion').to_pylist(),['unknown']*12)
  m=result['moments'][0];request=SelectMoment(project_path=str(self.manifest),expected_label_manifest_sha256=result['manifest_sha256'],moment_id=m['moment_id'],source_frame=m['source_frame'],timestamp_ns=m['timestamp_ns'],selected=True)
  selected=save_selection(request);self.assertEqual(selected['selected_moment_ids'],[m['moment_id']]);self.assertEqual(selection_view(self.manifest),selected)
  with self.assertRaises(HTTPException) as stale:save_selection(request)
  self.assertEqual(stale.exception.status_code,409)
  second=self.run_job();self.assertEqual(run_result(first)['result']['path'],result['path']);self.assertNotEqual(run_result(second)['result']['path'],result['path'])
  self.assertEqual(registry.get(first).snapshot()['status'],'complete')
 def test_stale_and_changed_image_fail_without_publication(self):
  request=self.generate().model_copy(update={'expected_pose_manifest_sha256':'0'*64})
  with self.assertRaises(HTTPException) as stale:start_labels(request)
  self.assertEqual(stale.exception.status_code,409)
  (self.result/'frames/000010-left.png').write_bytes(b'changed')
  run=self.run_job();self.assertEqual(registry.get(run).snapshot()['status'],'failed');self.assertIsNone(read_model(self.manifest,Project).label_result)
 def test_cancel_and_competing_run(self):
  import threading
  entered=threading.Event()
  def hold(bound,work,ctx):
   entered.set()
   while True:ctx.check_cancelled();time.sleep(.005)
  with patch('skellyclicker_app.label_pipeline.projection_source',side_effect=hold):
   first=start_labels(self.generate())['run_id'];self.assertTrue(entered.wait(5))
   with self.assertRaises(HTTPException) as conflict:start_labels(self.generate())
   self.assertEqual(conflict.exception.status_code,409)
   registry.get(first).cancel();jobs[first]['thread'].join(5)
  self.assertEqual(registry.get(first).snapshot()['status'],'cancelled');self.assertIsNone(read_model(self.manifest,Project).label_result)

if __name__=='__main__':unittest.main()
