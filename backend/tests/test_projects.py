"""Fresh project invariants: relocation, immutable source, failed open and traversal rejection."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from skellyclicker_app.manual_recording import OpenFolder
from skellyclicker_app.project_routes import open_workspace_folder
from skellyclicker_app.projects import CreateProject, create_project, open_project

class ProjectsTest(unittest.TestCase):
    def test_folder_picker_opens_recording_without_project(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            root = parent / 'test-recording'
            synchronized = root / 'synchronized_videos'
            synchronized.mkdir(parents=True)
            for camera in ('Cam1', 'Cam2', 'Cam3'):
                writer = cv2.VideoWriter(str(synchronized / f'{camera}.avi'),
                                         cv2.VideoWriter_fourcc(*'MJPG'), 30, (32, 24))
                try:
                    self.assertTrue(writer.isOpened())
                    writer.write(np.zeros((24, 32, 3), dtype=np.uint8))
                finally:
                    writer.release()
            for folder in (root, synchronized):
                result = open_workspace_folder(OpenFolder(path=str(folder)))
                self.assertEqual(result['root'], str(root))
                self.assertEqual(len(result['sourceSizes']), 3)
            self.assertEqual(open_workspace_folder(OpenFolder(path=str(parent)))['candidates'],
                             [{'name': root.name, 'path': str(root)}])
            self.assertFalse(list(root.glob('*_project.json')))

    def test_create_relocate_missing_and_changed_source(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            capture = base / 'capture'; capture.mkdir()
            source = capture / 'stereo.svo2'; source.write_bytes(b'original stereo')
            cal = capture / 'camera.conf'; cal.write_text('calibration')
            stl = base / 'reference.stl'; stl.write_bytes(b'original geometry')
            root = base / 'fresh-project'
            request = CreateProject(project_path=str(root), source_svo=str(source), calibration_source=str(cal), source_stl=str(stl), object_id='arbitrary-object')
            created = create_project(request)
            self.assertEqual(created['issues'], [])
            canonical = 'recordings/capture/skellyclicker/inputs/targets/arbitrary-object/r001/arbitrary-object.stl'
            self.assertEqual(created['targets'][0]['geometry']['path'], canonical)
            self.assertEqual((root/canonical).read_bytes(), stl.read_bytes())
            stl.unlink()  # Reopening must use the copied target, not its original path.
            self.assertEqual(open_project(root)['issues'], [])
            self.assertEqual(created['recordings'][0]['calibration_state'], 'unqueried')
            self.assertEqual(source.read_bytes(), b'original stereo')
            moved = base / 'renamed-folder'; root.rename(moved)
            reopened = open_project(moved)
            with patch.dict('os.environ', SKELLYCLICKER_SESSION_PATH=str(base / 'session.json')):
                picked = open_workspace_folder(OpenFolder(path=str(moved)))
                self.assertEqual(picked['project']['manifest_path'], reopened['manifest_path'])
            self.assertEqual(reopened['project']['uuid'], created['project']['uuid'])
            self.assertEqual(reopened['project']['project_id'], 'fresh-project')
            self.assertTrue((moved/'fresh-project_project.json').is_file())
            source.write_bytes(b'different stereo')
            self.assertIn('Changed source', open_project(moved)['issues'][0])
            source.unlink()
            self.assertIn('Missing source', open_project(moved)['issues'][0])
            manifest = moved/'fresh-project_project.json'
            data = json.loads(manifest.read_text()); data['target_manifests']=['../outside.json']
            manifest.write_text(json.dumps(data))
            with self.assertRaises(ValueError): open_project(moved)
            absent = base/'does-not-exist'
            with self.assertRaises(ValueError): open_project(absent)
            self.assertFalse(absent.exists())

if __name__ == '__main__': unittest.main()
