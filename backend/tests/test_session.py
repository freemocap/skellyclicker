import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException
from skellyclicker_app import session
from skellyclicker_app.projects import CreateProject, create_project

class SessionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root/'settings'/'session.json'
        self.env = patch.dict('os.environ', {'SKELLYCLICKER_SESSION_PATH': str(self.path)})
        self.env.start()
    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()
    def project(self):
        source=self.root/'capture.svo2';source.write_bytes(b'source')
        cal=self.root/'camera.conf';cal.write_text('calibration')
        stl=self.root/'target.stl';stl.write_bytes(b'geometry')
        return create_project(CreateProject(project_path=str(self.root/'project'),source_svo=str(source),calibration_source=str(cal),source_stl=str(stl),object_id='arbitrary'))
    def test_restore_from_disk_preserves_project_bytes_and_navigation(self):
        project=self.project();manifest=Path(project['manifest_path']);original=manifest.read_bytes()
        session.remember_project(project)
        session.update_session(session.SessionUpdate(project_path=str(manifest),workspace='training',sidebar='project',training_run_id='saved-run'))
        restored=session.restore_session()
        self.assertIsNone(restored['error'])
        self.assertEqual(restored['state']['workspace'],'training')
        self.assertEqual(restored['state']['training_run_id'],'saved-run')
        self.assertEqual(restored['state']['recording_id'],project['recordings'][0]['recording_id'])
        self.assertEqual(manifest.read_bytes(),original)
        session.remember_project(project)
        self.assertEqual(session.read_session().training_run_id,'saved-run')
    def test_missing_project_retains_session_and_reports_recovery(self):
        project=self.project();session.remember_project(project)
        saved=self.path.read_bytes();Path(project['manifest_path']).rename(self.root/'moved.json')
        restored=session.restore_session()
        self.assertIsNone(restored['project'])
        self.assertIn('Open its current location or retry',restored['error'])
        self.assertEqual(self.path.read_bytes(),saved)
    def test_recent_projects_survive_restart_and_include_legacy_session(self):
        self.path.parent.mkdir()
        self.path.write_text(json.dumps({"version":1,"project_path":"first"}))
        self.assertEqual(session.recent_projects(), ["first"])
        for path in ("second","third","second"):
            session.remember_project({"manifest_path":path,"recordings":[]})
        self.assertEqual(session.recent_projects(), ["second","third","first"])
        self.assertEqual(json.loads(self.path.read_text())["recent_projects"], session.recent_projects())

    def test_stale_update_cannot_overwrite_new_project(self):
        session.remember_project({'manifest_path':'new-project','recordings':[{'recording_id':'recording'}]})
        with self.assertRaises(HTTPException) as problem:
            session.update_session(session.SessionUpdate(project_path='old-project',workspace='training'))
        self.assertEqual(problem.exception.status_code,409)
        self.assertEqual(session.read_session().workspace,'viewer')
    def test_corrupt_session_is_not_silently_discarded(self):
        self.path.parent.mkdir();self.path.write_text('{broken')
        restored=session.restore_session()
        self.assertIn('Cannot read saved session',restored['error'])
        self.assertEqual(self.path.read_text(),'{broken')
