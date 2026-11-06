"""Explicit, additive correction of a project's consumed target location."""
import json
from pathlib import Path
import shutil
from uuid import uuid4
from freemocap_sdk.storage import atomic_json, file_digest, resolve_relative, project_lock, publish_directory
from .projects import Project, Recording, read_model, load_target, target_directory, artifact, recording_structure


def canonicalize_target(manifest: Path) -> dict:
    manifest = manifest.resolve(); root = manifest.parent
    before = manifest.read_bytes(); project = Project.model_validate_json(before)
    if len(project.recording_manifests) != 1 or len(project.target_manifests) != 1:
        raise ValueError('Select exactly one recording and target for this operation.')
    recording = read_model(resolve_relative(root, project.recording_manifests[0]), Recording)
    target = load_target(root, project.target_manifests[0])
    destination = target_directory(root, recording.recording_id, target.object_id, target.revision)
    target_manifest = destination / f'{target.object_id}_target.json'
    relative = target_manifest.relative_to(root).as_posix()
    if project.target_manifests == [relative]:
        return {'changed': False, 'target_manifest': relative, 'stl': target.geometry.path}
    update = recording_structure(root, recording.recording_id).application_dir('skellyclicker')/'updates'/('target-location-'+uuid4().hex[:12])
    staged = update/'snapshot'; staged.mkdir(parents=True)
    def copy_checked(value, name):
        source = resolve_relative(root, value.path)
        if file_digest(source) != value.sha256 or source.stat().st_size != value.bytes:
            raise ValueError(f'Changed input: {source}')
        output = staged/name
        shutil.copyfile(source, output)
        if file_digest(output) != value.sha256: raise ValueError('Snapshot copy changed')
        return artifact(output, name)
    geometry = copy_checked(target.geometry, f'{target.object_id}.stl')
    authored = None
    if target.authored_geometry:
        source_manifest = resolve_relative(root, target.authored_geometry.path)
        if file_digest(source_manifest) != target.authored_geometry.sha256:
            raise ValueError('Changed authored target manifest')
        spec = json.loads(source_manifest.read_text())
        from .projects import Artifact
        for key, name in [('keypoints','keypoints.json'), ('outline','outline.bin')]:
            value = Artifact.model_validate(spec[key])
            if spec.get('path_basis') == 'target_directory':
                value = value.model_copy(update={'path': resolve_relative(source_manifest.parent,value.path).relative_to(root).as_posix()})
            spec[key] = copy_checked(value,name).model_dump(mode='json')
        spec['path_basis'] = 'target_directory'
        atomic_json(staged/'authored_geometry.json', spec)
        authored = artifact(staged/'authored_geometry.json', 'authored_geometry.json')
    snapshot = target.model_copy(update={'path_basis':'target_directory','geometry':geometry,'authored_geometry':authored})
    atomic_json(staged/target_manifest.name, snapshot.model_dump(mode='json'))
    atomic_json(update/'provenance.json', {'previous_target_manifest':project.target_manifests[0],
        'target_manifest':relative,'source_stl_sha256':target.geometry.sha256,
        'previous_authored_geometry_sha256':target.authored_geometry.sha256 if target.authored_geometry else None,
        'reason':'Recording-local consumed target snapshot; geometry and point identities unchanged.'})
    with project_lock(root):
        if manifest.read_bytes() != before: raise ValueError('Project changed during snapshot; reopen before retrying.')
        if destination.exists(): raise FileExistsError(f'Target snapshot already exists: {destination}')
        destination.parent.mkdir(parents=True,exist_ok=True)
        publish_directory(staging=staged,destination=destination)
        (update/'previous_project.json').write_bytes(before)
        project.target_manifests=[relative]
        atomic_json(manifest, project.model_dump(mode='json'))
    return {'changed':True,'target_manifest':relative,'stl':(destination/geometry.path).relative_to(root).as_posix(),'rollback':str(update/'previous_project.json')}
