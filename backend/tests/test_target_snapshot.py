import json, tempfile, unittest
from pathlib import Path
import trimesh
from skellyclicker_app.projects import CreateProject,create_project,read_model,Project,load_target,artifact
from skellyclicker_app.target_snapshot import canonicalize_target
from skellyclicker_app.stl_selection import ValidateStl,validate_stl
from skellyclicker_app.authored_geometry import load_authored_geometry

class TargetSnapshotTest(unittest.TestCase):
    def test_create_default_and_explicit_correction_preserve_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);capture=base/'capture';capture.mkdir()
            (capture/'stereo.svo2').write_bytes(b'original');(capture/'cal.conf').write_text('cal')
            stl=base/'part.stl';stl.write_bytes(trimesh.creation.box().export(file_type='stl'))
            view=create_project(CreateProject(project_path=str(base/'project'),source_svo=str(capture/'stereo.svo2'),calibration_source=str(capture/'cal.conf'),source_stl=str(stl),object_id='part'))
            root=Path(view['root']);manifest=Path(view['manifest_path']);project=read_model(manifest,Project)
            canonical='recordings/capture/skellyclicker/inputs/targets/part/r001/part_target.json'
            self.assertEqual(project.target_manifests,[canonical])
            self.assertTrue(validate_stl(ValidateStl(project_path=str(manifest)))['compatible'])
            # Model the pre-correction library layout without deleting the created snapshot.
            target=load_target(root,canonical);library=root/'targets/part/r002';library.mkdir(parents=True)
            (library/'part.stl').write_bytes(stl.read_bytes())
            points={'units':'mm','source_stl_sha256':target.geometry.sha256,'points':[{'group':'g','name':str(i),'xyz_mm':p} for i,p in enumerate([[0,0,0],[1,0,0],[0,1,0]])],'connections':[{'ids':[0,1,2],'closed':True}]}
            (library/'keypoints.json').write_text(json.dumps(points));(library/'outline.bin').write_bytes(b'outline')
            def ref(name):return artifact(library/name,(library/name).relative_to(root).as_posix()).model_dump()
            (library/'authored_geometry.json').write_text(json.dumps({'source_stl_sha256':target.geometry.sha256,'keypoints':ref('keypoints.json'),'outline':ref('outline.bin'),'origin_mm':[0,0,0]}))
            target=target.model_copy(update={'revision':'r002','geometry':artifact(library/'part.stl','targets/part/r002/part.stl'),'authored_geometry':artifact(library/'authored_geometry.json','targets/part/r002/authored_geometry.json')})
            (library/'part_target.json').write_text(target.model_dump_json());project.target_manifests=['targets/part/r002/part_target.json'];manifest.write_text(project.model_dump_json())
            before={p.name:p.read_bytes() for p in library.iterdir()}
            result=canonicalize_target(manifest);self.assertTrue(result['changed'])
            new_project=read_model(manifest,Project);new_target=load_target(root,new_project.target_manifests[0])
            self.assertEqual(new_target.geometry.sha256,target.geometry.sha256)
            self.assertEqual(load_authored_geometry(root,new_target)['names'],('g / 0','g / 1','g / 2'))
            self.assertTrue(validate_stl(ValidateStl(project_path=str(manifest)))['compatible'])
            self.assertFalse(canonicalize_target(manifest)['changed'])
            self.assertEqual(json.loads(Path(result['rollback']).read_text())['target_manifests'],['targets/part/r002/part_target.json'])
            for name,content in before.items():self.assertEqual((library/name).read_bytes(),content)
            moved=base/'relocated';root.rename(moved)
            self.assertTrue(validate_stl(ValidateStl(project_path=str(moved/manifest.name)))['compatible'])
            self.assertEqual(stl.read_bytes(),(moved/new_target.geometry.path).read_bytes())

if __name__=='__main__':unittest.main()
