"""Reuse a frozen backend only when its inputs and on-disk bundle match."""
import hashlib
import json
import os
import platform
import subprocess
import sys
import tomllib
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
WORK = ROOT / ".test-artifacts" / "desktop-bundle"
OUTPUT = ROOT / "native" / "binaries"
NAME = "skellyclicker-backend"


def editable_roots():
    for package in tomllib.loads((BACKEND / "uv.lock").read_text(encoding="utf-8"))["package"]:
        editable = package["source"].get("editable")
        if editable is not None:
            yield (BACKEND / editable).resolve()


def source_digest():
    files = {Path(__file__), ROOT / "tools/prepare-desktop.mjs", ROOT / "tools/smoke-installed.py",
             BACKEND / "desktop_entry.py", BACKEND / ".python-version", BACKEND / "uv.lock"}
    # Editable package code and package data can change without a lockfile change.
    for root in editable_roots():
        files.add(root / "pyproject.toml")
        for base in (root, root / "src"):
            if base.is_dir():
                for init in base.glob("*/__init__.py"):
                    for directory, subdirs, names in os.walk(init.parent):
                        subdirs[:] = [name for name in subdirs if name not in (".venv", "__pycache__")]
                        files.update(Path(directory) / name for name in names if not name.endswith((".pyc", ".pyo")))
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(str(path).encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    runtime = (sys.version, sys.platform, platform.machine(), version("pyinstaller"))
    digest.update(repr(runtime).encode())
    return digest.hexdigest()


def bundle_inventory():
    folder = OUTPUT / NAME
    executable = folder / (NAME + (".exe" if os.name == "nt" else ""))
    if not executable.is_file() or not (folder / "_internal").is_dir():
        return None
    entries = {}
    for path in folder.rglob("*"):
        if path.is_file():
            stat = path.stat()
            entries[path.relative_to(folder).as_posix()] = [stat.st_size, stat.st_mtime_ns]
    return entries


@contextmanager
def build_lock():
    WORK.mkdir(parents=True, exist_ok=True)
    with (WORK / "prepare.lock").open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            import time
            import errno
            handle.seek(0)
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if exc.errno != errno.EACCES:
                        raise
                    time.sleep(.25)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def prepare(*, force):
    state_file = WORK / "dev-state.json"
    with build_lock():
        inputs = source_digest()
        try:
            saved = json.loads(state_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            saved = None
        if not force and isinstance(saved, dict) and saved.get("inputs") == inputs:
            inventory = bundle_inventory()
            if inventory and inventory == saved.get("bundle"):
                print("Backend is current. Reusing the existing bundle.", flush=True)
                return
        state_file.unlink(missing_ok=True)
        print("Building SkellyClicker backend…", flush=True)
        # PyInstaller's static analysis cannot follow setuptools editable import finders.
        search_paths = [str(base) for root in editable_roots() for base in (root, root / "src") if base.is_dir()]
        if os.environ.get("PYTHONPATH"):
            search_paths.append(os.environ["PYTHONPATH"])
        app = BACKEND / "skellyclicker_app"
        resources = [*sorted((app / "workers").glob("*.*")), *sorted((app / "gpu").glob("*/pyproject.toml")),
                     *sorted((app / "gpu").glob("*/uv.lock"))]
        subprocess.run([
            sys.executable, "-m", "freemocap_sdk.bundle", "--entrypoint", str(BACKEND / "desktop_entry.py"),
            "--name", NAME, "--output", str(OUTPUT), "--work", str(WORK),
            *[arg for path in resources for arg in ("--add-data", f"{path}:{path.parent.relative_to(BACKEND).as_posix()}")],
            "--collect-data", "skellyforge", "--collect-data", "skellytracker",
        ], cwd=ROOT, env={**os.environ, "PYTHONPATH": os.pathsep.join(search_paths)}, check=True)
        executable = OUTPUT / NAME / (NAME + (".exe" if os.name == "nt" else ""))
        subprocess.run([sys.executable, str(ROOT / "tools/smoke-installed.py"), "--backend-only", str(executable)],
                       check=True)
        inventory = bundle_inventory()
        if not inventory or source_digest() != inputs:
            raise RuntimeError("Backend build incomplete or inputs changed during the build. Run again.")
        pending = state_file.with_suffix(".tmp")
        pending.write_text(json.dumps({"inputs": inputs, "bundle": inventory}), encoding="utf-8")
        pending.replace(state_file)


if __name__ == "__main__":
    prepare(force="--force" in sys.argv[1:])
