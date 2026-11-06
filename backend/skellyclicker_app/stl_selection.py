"""Read-only validation of an STL draft, without replacing project artifacts."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Literal

import numpy as np
import trimesh
from freemocap_sdk.storage import resolve_relative
from .projects import Model, Project, Target, read_model, load_target


class ValidateStl(Model):
    project_path: str
    path: str | None = None
    authored_units: Literal["mm", "m"] | None = None


def validate_stl(request: ValidateStl) -> dict:
    manifest = Path(request.project_path).expanduser().resolve()
    if manifest.is_dir():
        matches = list(manifest.glob("*_project.json"))
        if len(matches) != 1:
            raise ValueError("Select the exact project manifest.")
        manifest = matches[0]
    project = read_model(manifest, Project)
    if manifest.name != f"{project.project_id}_project.json":
        raise ValueError("Project manifest filename must match its stored project ID.")
    if len(project.target_manifests) != 1:
        raise ValueError("STL selection requires a project with one target.")
    target = load_target(manifest.parent, project.target_manifests[0])
    current = resolve_relative(manifest.parent, target.geometry.path).resolve()
    path = Path(request.path).expanduser() if request.path is not None else current
    if not path.is_absolute():
        raise ValueError("Select an absolute STL file path.")
    path = path.resolve()
    if path.suffix.lower() != ".stl" or not path.is_file():
        raise ValueError(f"Select an existing STL file: {path}")
    # Hash and parse the same bytes. Units are declared; STL does not encode them.
    contents = path.read_bytes()
    try:
        mesh = trimesh.load(BytesIO(contents), file_type="stl", force="mesh", process=False)
        valid = (isinstance(mesh, trimesh.Trimesh) and len(mesh.vertices) > 0
                 and len(mesh.faces) > 0 and np.isfinite(mesh.vertices).all()
                 and np.isfinite(mesh.area) and mesh.area > 0)
    except Exception as error:
        raise ValueError("The selected file cannot be read as STL geometry.") from error
    if not valid:
        raise ValueError("The STL must contain finite, non-empty surface geometry.")
    digest = sha256(contents).hexdigest()
    units = request.authored_units or target.authored_units
    # Identical external files resolve to the project-owned snapshot, never a
    # historical source path. Different geometry remains an explicit draft.
    if digest == target.geometry.sha256 and current.is_file() and sha256(current.read_bytes()).hexdigest() == digest:
        path = current
    return {"path": str(path), "current_path": str(current), "sha256": digest,
            "bytes": len(contents), "authored_units": units,
            "vertices": len(mesh.vertices), "faces": len(mesh.faces),
            "compatible": digest == target.geometry.sha256 and units == target.authored_units}
