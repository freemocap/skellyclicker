"""Recording publication retains original media and complete source-frame identity."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from skellyclicker_app.projects import CreateProject,create_project,read_model,Recording,recording_structure
from skellyclicker_app.recording_layout import ensure_recording_inputs

class RecordingLayoutTest(unittest.TestCase):
 def test_staged_inputs_and_idempotent_verified_reuse(self):
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);capture=base/'capture';capture.mkdir()
   source=capture/'stereo.svo2';source.write_bytes(b'original')
   calibration=capture/'camera.conf';calibration.write_bytes(b'factory')
   mesh=base/'shape.stl';mesh.write_bytes(b'mesh')
   view=create_project(CreateProject(project_path=str(base/'project'),source_svo=str(source),calibration_source=str(calibration),source_stl=str(mesh)))
   root=Path(view['root']);paths=recording_structure(root,'capture')
   self.assertEqual(root/view['project']['recording_manifests'][0],paths.stereo_manifest_path)
   recording=read_model(paths.stereo_manifest_path,Recording)
   def decode(job,*args):
    request=job['request'];out=job['output']
    for video in request['videos'].values():
     target=Path(video);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'decoded-video')
    K=[[500,0,320],[0,500,240],[0,0,1]]
    cal={'source_frame_count':2,'nominal_fps':30,'image_width':640,'image_height':480,'left':K,'right':K,'T_left_from_right_m':[[1,0,0,.12],[0,1,0,0],[0,0,1,0],[0,0,0,1]]}
    (out/'calibration.json').write_text(json.dumps(cal),encoding='utf-8')
    (out/'samples.json').write_text(json.dumps([{'source_frame':0,'timestamp_ns':1700000000000000001},{'source_frame':1,'timestamp_ns':1700000000033333334}]),encoding='utf-8')
   probe=json.dumps({'streams':[{'nb_frames':'2','width':640,'height':480}]}).encode()
   with patch('skellyclicker_app.preparation.runtime_config',return_value={'zed_python':'unused'}),patch('skellyclicker_app.preparation.run_worker',side_effect=decode) as worker,patch('skellyclicker_app.recording_layout.subprocess.check_output',return_value=probe),patch('skellyclicker_app.recording_layout.shutil.which',return_value='ffmpeg'):
    info=ensure_recording_inputs(root,recording)
    self.assertEqual(info['frame_count'],2)
    self.assertEqual(info['videos'],{'left':'left.mp4','right':'right.mp4'})
    self.assertEqual(ensure_recording_inputs(root,recording),info)
    self.assertEqual(worker.call_count,1)
   clock=json.loads(paths.source_timing_path.read_text(encoding='utf-8'))
   self.assertEqual(clock['timestamps_ns'],[1700000000000000001,1700000000033333334])
   self.assertFalse(paths.data_parquet_path.exists())
   self.assertEqual(source.read_bytes(),b'original')
   self.assertEqual(calibration.read_bytes(),b'factory')
   (paths.videos_synchronized_dir/'left.mp4').write_bytes(b'changed')
   with self.assertRaises(ValueError):ensure_recording_inputs(root,recording)
