"""Draft selection must not mutate manifests or reuse incompatible geometry."""
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
import trimesh
from skellyclicker_app.projects import Project, Target, Artifact
from skellyclicker_app.stl_selection import ValidateStl, validate_stl


class StlSelectionTest(unittest.TestCase):
    def test_identity_units_and_invalid_files_leave_project_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stl = root / "target.stl"
            stl.write_bytes(trimesh.creation.box().export(file_type="stl"))
            target = Target(object_id="object", authored_units="mm", source_path=str(stl),
                geometry=Artifact(path=stl.name, sha256=sha256(stl.read_bytes()).hexdigest(), bytes=stl.stat().st_size))
            (root / "target.json").write_text(target.model_dump_json())
            manifest = root / "project_project.json"
            manifest.write_text(Project(project_id="project", recording_manifests=[], target_manifests=["target.json"]).model_dump_json())
            before = {p.name:p.read_bytes() for p in root.iterdir()}
            def check(path=None, units=None):
                return validate_stl(ValidateStl(project_path=str(manifest), path=str(path) if path is not None else None, authored_units=units))
            self.assertTrue(check()["compatible"])
            self.assertEqual(check()["path"], str(stl.resolve()))
            copy = root / "copy.stl"; copy.write_bytes(stl.read_bytes())
            self.assertTrue(check(copy)["compatible"])
            self.assertEqual(check(copy)["path"], str(stl.resolve()))
            self.assertFalse(check(copy, "m")["compatible"])
            copy.write_bytes(trimesh.creation.box(extents=[2, 3, 4]).export(file_type="stl"))
            self.assertFalse(check(copy)["compatible"])
            for name, contents in [("invalid.stl", b"not an stl"), ("wrong.obj", b"wrong extension"), ("empty.stl", b"")]:
                bad = root / name; bad.write_bytes(contents)
                with self.assertRaises(ValueError): check(bad)
            with self.assertRaises(ValueError): check(root / "missing.stl")
            with self.assertRaises(ValueError): check(Path("relative.stl"))
            for name, contents in before.items():
                self.assertEqual((root/name).read_bytes(), contents)


if __name__ == "__main__": unittest.main()
