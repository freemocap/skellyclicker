import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from pydantic import ValidationError
import pyarrow.parquet as pq
from skellyclicker_app.projects import CreateProject,create_project
from skellyclicker_app.preparation import PreparationRequest,publish_result

class PreparationTest(unittest.TestCase):
 def test_bounded_range(self):
  for count in (0,901):
   with self.assertRaises(ValidationError):PreparationRequest(project_path='x',frame_count=count)
 def test_publication_preserves_later_pose_and_integer_clock(self):
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);capture=base/'capture';capture.mkdir()
   source=capture/'stereo.svo2';source.write_bytes(b'source');cal=capture/'camera.conf';cal.write_text('cal');stl=base/'mesh.stl';stl.write_bytes(b'mesh')
   view=create_project(CreateProject(project_path=str(base/'project'),source_svo=str(source),calibration_source=str(cal),source_stl=str(stl)))
   root=Path(view['root']);work=root/'working'/'test';output=work/'output';output.mkdir(parents=True)
   rows=[{'source_frame':0,'timestamp_ns':1700000000000000001,'accepted':False,'status':'no_mask'}, {'source_frame':1,'timestamp_ns':1700000000033333334,'accepted':True,'status':'accepted','T_left_from_stl_m':[[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,1.],[0.,0.,0.,1.]]}]
   for name,value in {'candidates.json':rows,'calibration.json':{},'geometry.json':{},'replay-software.json':{},'pose-software.json':{}}.items():(output/name).write_text(json.dumps(value))
   for name in ('zed_replay','fit_pose'):(work/(name+'.py')).write_text('pass')
   request={'frame_count':2,'start_frame':0,'recording_id':'capture','source_sha256':view['recordings'][0]['source']['sha256'],'target_sha256':view['targets'][0]['geometry']['sha256'],'mask_preset':'test'}
   job={'root':root,'work':work,'output':output,'manifest':Path(view['manifest_path']),'request':request,'status':{'job_id':'test'},'cancel':threading.Event()}
   with patch('skellyclicker_app.playback_adapter.build_project_playback'):
    publish_result(job)
   result=root/job['status']['result'];table=pq.read_table(result/'candidates.parquet')
   self.assertEqual(table['T_left_from_stl_m'].to_pylist(),[None,rows[1]['T_left_from_stl_m']])
   self.assertEqual(pq.read_table(result/'timing.parquet')['timestamp_ns'].to_pylist(),[r['timestamp_ns'] for r in rows])
   self.assertEqual(source.read_bytes(),b'source')
   self.assertEqual(json.loads(Path(view['manifest_path']).read_text())['sample_result'],job['status']['result'])

if __name__=='__main__':unittest.main()
