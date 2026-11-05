"""Fresh project invariants: relocation, immutable source, failed open and traversal rejection."""
from pathlib import Path
import json
import tempfile
import unittest
from skellyclicker_app.projects import CreateProject, create_project, open_project

class ProjectsTest(unittest.TestCase):
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
            self.assertEqual(created['recordings'][0]['calibration_state'], 'unqueried')
            self.assertEqual(source.read_bytes(), b'original stereo')
            moved = base / 'renamed-folder'; root.rename(moved)
            reopened = open_project(moved)
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
