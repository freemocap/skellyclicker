import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException
from skellyclicker_app.quality_routes import QualityRequest,rank_rows,BulkSelection,bulk_selection,quality_preview
from skellyclicker_app.label_routes import result_view,selection_view
import test_labels

class RankingTest(unittest.TestCase):
 def request(self,**kw):return QualityRequest(project_path='fixture',expected_label_manifest_sha256='label',expected_selection_sha256='selection',**kw)
 def fixture(self):
  images=[dict(image_id=str(i)+':'+c,moment_id=str(i),source_frame=i,camera_id=c,timestamp_ns=str(i*100000000)) for i in range(4) for c in ('left','right')]
  candidates={i:dict(accepted=True,left_iou=.9,right_iou=.85,left_mask_fraction=.95,right_mask_fraction=.95,depth_coverage=.9,common_depth_px=200,median_abs_depth_mm=1) for i in range(4)}
  labels=[dict(moment_id=r['moment_id'],camera_id=r['camera_id'],projection_valid=True,in_bounds=True,x_px=10,y_px=20) for r in images]
  return images,candidates,labels
 def test_deterministic_count_camera_identity_and_spacing(self):
  images,candidates,labels=self.fixture();q=self.request(top_n=3)
  rows,ids=rank_rows(images,candidates,labels,q);self.assertEqual(ids,['0:left','1:left','2:left'])
  self.assertEqual(rank_rows(list(reversed(images)),candidates,labels,q)[1],ids)
  ids=rank_rows(images,candidates,labels,self.request(top_n=4,spacing_seconds=.2))[1]
  self.assertEqual(ids,['0:left','2:left','0:right','2:right'])
 def test_missing_and_bad_do_not_fill_requested_count(self):
  images,candidates,labels=self.fixture();candidates[0]['median_abs_depth_mm']=None;candidates[1]['left_iou']=.1;candidates[2]['accepted']=False;candidates[3]['depth_coverage']=.1
  rows,ids=rank_rows(images,candidates,labels,self.request(top_n=100));self.assertEqual(ids,['1:right']);self.assertIsNone(rows[-1]['score']);self.assertTrue(rows[-1]['unknown'])
 def test_relaxed_individual_gates_require_explicit_fit_gate_off(self):
  images,candidates,labels=self.fixture()
  for c in candidates.values():c.update(accepted=False,left_iou=.6,right_iou=.6)
  self.assertEqual(rank_rows(images,candidates,labels,self.request(min_iou=.5))[1],[])
  self.assertEqual(len(rank_rows(images,candidates,labels,self.request(min_iou=.5,require_fit_passed=False))[1]),8)

class BulkTest(unittest.TestCase):
 setUp=test_labels.LabelsTest.setUp
 tearDown=test_labels.LabelsTest.tearDown
 generate=test_labels.LabelsTest.generate
 run_job=test_labels.LabelsTest.run_job
 def bulk_request(self,operation,ids):
  r=result_view(self.manifest);s=selection_view(self.manifest)
  return BulkSelection(project_path=str(self.manifest),expected_label_manifest_sha256=r['manifest_sha256'],expected_selection_sha256=s['sha256'],operation=operation,image_ids=ids)
 def test_atomic_remove_keep_restore_and_stale_guard(self):
  self.run_job();old=selection_view(self.manifest);ids=old['selected_image_ids'];request=self.bulk_request('remove',ids[:2]);result=bulk_selection(request)
  self.assertEqual(result['receipt']['removed_count'],2);self.assertEqual(result['selected_image_ids'],ids[2:])
  with self.assertRaises(HTTPException):bulk_selection(request)
  with self.assertRaises(HTTPException):bulk_selection(self.bulk_request('keep',[ids[0]]))
  r=bulk_selection(self.bulk_request('keep',[ids[-1]]));self.assertEqual(r['selected_image_ids'],[ids[-1]])
  r=bulk_selection(self.bulk_request('restore',ids[:1]));self.assertEqual(set(r['selected_image_ids']),{ids[0],ids[-1]})
 def test_failed_commit_keeps_membership_and_manifest(self):
  self.run_job();before=self.manifest.read_bytes();old=selection_view(self.manifest)
  with patch('skellyclicker_app.quality_routes.atomic_json',side_effect=OSError('fixture failure')):
   with self.assertRaises(HTTPException):bulk_selection(self.bulk_request('remove',old['selected_image_ids'][:2]))
  self.assertEqual(self.manifest.read_bytes(),before);self.assertEqual(selection_view(self.manifest),old)
 def test_empty_keep_and_noop_do_not_reinclude(self):
  self.run_job();r=bulk_selection(self.bulk_request('keep',[]));self.assertEqual(r['selected_image_ids'],[])
  again=bulk_selection(self.bulk_request('keep',[]));self.assertEqual(again['sha256'],r['sha256'])

 def test_preview_apply_provenance_and_changed_preview_rejected(self):
  import json,pyarrow as pa,pyarrow.parquet as pq
  from freemocap_sdk.storage import atomic_json,inventory
  rows=pq.read_table(self.result/'candidates.parquet').to_pylist()
  for r in rows:r.update(left_iou=.9,right_iou=.85,left_mask_fraction=.9,right_mask_fraction=.9,depth_coverage=.8,common_depth_px=150,median_abs_depth_mm=2)
  pq.write_table(pa.Table.from_pylist(rows),self.result/'candidates.parquet')
  meta=json.loads((self.result/'manifest.json').read_text());meta['files']={k:v.model_dump() for k,v in inventory(self.result).items() if k!='manifest.json'};atomic_json(self.result/'manifest.json',meta)
  self.run_job();r=result_view(self.manifest);sel=selection_view(self.manifest)
  q=QualityRequest(project_path=str(self.manifest),expected_label_manifest_sha256=r['manifest_sha256'],expected_selection_sha256=sel['sha256'],top_n=2,min_in_bounds_fraction=.5,selection_mode='quality_only')
  before=self.manifest.read_bytes();preview=quality_preview(q);self.assertEqual(self.manifest.read_bytes(),before);self.assertEqual(len(preview['image_ids']),2)
  request=self.bulk_request('keep',preview['image_ids']).model_copy(update={'preview_id':preview['preview_id']})
  with self.assertRaises(HTTPException):bulk_selection(request.model_copy(update={'image_ids':preview['image_ids'][:1]}))
  result=bulk_selection(request);self.assertEqual(result['receipt']['after_count'],2);self.assertEqual(result['receipt']['ranking']['policy']['top_n'],2)
  with self.assertRaises(HTTPException):bulk_selection(request)

 def test_3038_image_bulk_selection_preserves_labels_and_previous_revision(self):
  import json,time,pyarrow as pa,pyarrow.parquet as pq
  from freemocap_sdk.storage import atomic_json,inventory,file_digest
  from skellyclicker_app.projects import read_model,Project
  from skellyclicker_app.selection_storage import write_selection
  self.run_job();result=result_view(self.manifest);folder=self.root/result['path'];templates=pq.read_table(folder/'images.parquet').to_pylist();label=pq.read_table(folder/'labels.parquet').to_pylist()[0]
  moments=[dict(moment_id='moment-'+str(i),source_frame=i,timestamp_ns=10**18+i*33333333,fit_passed=True,fit_status='accepted') for i in range(1519)]
  images=[dict(templates[c],moment_id=m['moment_id']) for m in moments for c in range(2)]
  labels=[dict(label,moment_id=r['moment_id'],camera_id=r['camera_id'],keypoint_index=k) for r in images for k in range(52)]
  for name,rows in [('images',images),('moments',moments),('labels',labels)]:pq.write_table(pa.Table.from_pylist(rows),folder/(name+'.parquet'))
  meta=json.loads((folder/'manifest.json').read_text());meta['files']={k:v.model_dump() for k,v in inventory(folder).items() if k!='manifest.json'};atomic_json(folder/'manifest.json',meta)
  result=result_view(self.manifest);project=read_model(self.manifest,Project);review=write_selection(self.root,'capture',result['path'],result['manifest_sha256'],result['images']);project.active_review=review;atomic_json(self.manifest,project.model_dump())
  prior=(self.root/review/'selection.parquet').read_bytes();label_hash=file_digest(folder/'labels.parquet');ids=[r['image_id'] for r in result['images']]
  request=self.bulk_request('remove',ids[100:200]);start=time.perf_counter();removed=bulk_selection(request);remove_ms=(time.perf_counter()-start)*1000
  self.assertEqual(removed['receipt']['after_count'],2938)
  request=self.bulk_request('keep',removed['selected_image_ids'][:100]);start=time.perf_counter();kept=bulk_selection(request);keep_ms=(time.perf_counter()-start)*1000
  self.assertEqual(kept['receipt']['after_count'],100);self.assertFalse(set(ids[100:200])&set(kept['selected_image_ids']))
  self.assertEqual(file_digest(folder/'labels.parquet'),label_hash);self.assertEqual((self.root/review/'selection.parquet').read_bytes(),prior)
  self.assertEqual(len(pq.read_table(folder/'labels.parquet')),3038*52)
  print(f'3038-image fixture: remove100 {remove_ms:.1f}ms; keep100 {keep_ms:.1f}ms;158k labels and prior revision unchanged')

 def test_thumbnail_context_reuses_membership_independent_inputs_and_rejects_changed_labels(self):
  from skellyclicker_app.label_routes import thumbnail_context,thumbnail_fingerprint
  from skellyclicker_app.projects import read_model,Project
  from freemocap_sdk.storage import atomic_json
  self.run_job();project=read_model(self.manifest,Project);play=self.root/'playback';play.mkdir()
  for name in ('inventory.json','provenance.json','playback.json','outline-projections.jsonl'):(play/name).write_text('{}')
  project.playback_result='playback';atomic_json(self.manifest,project.model_dump());fingerprint=thumbnail_fingerprint(self.manifest,project)
  args=(self.manifest,project.label_result,project.sample_result,project.playback_result,fingerprint)
  with patch('skellyclicker_app.label_routes.target_crop_metadata',return_value={'cameras':{}}) as crop:
   first=thumbnail_context(*args);second=thumbnail_context(*args);self.assertIs(first,second);self.assertEqual(crop.call_count,1)
   selected=selection_view(self.manifest);bulk_selection(self.bulk_request('remove',selected['selected_image_ids'][:1]))
   self.assertEqual(thumbnail_fingerprint(self.manifest,read_model(self.manifest,Project)),fingerprint)
   labels=self.root/project.label_result/'labels.parquet';labels.write_bytes(labels.read_bytes()+b'changed')
   changed=thumbnail_fingerprint(self.manifest,project);self.assertNotEqual(changed,fingerprint)
   with self.assertRaises(ValueError):thumbnail_context(*args[:-1],changed)
