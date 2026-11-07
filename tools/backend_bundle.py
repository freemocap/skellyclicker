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


def source_digest():
    lock = BACKEND / "uv.lock"
    files = {Path(__file__), ROOT / "tools/prepare-desktop.mjs",
             BACKEND / "desktop_entry.py", BACKEND / ".python-version", lock}
    # Editable package code and package data can change without a lockfile change.
    for package in tomllib.loads(lock.read_text(encoding="utf-8"))["package"]:
        editable = package["source"].get("editable")
        if editable is None:
            continue
        root = (BACKEND / editable).resolve()
        files.add(root / "pyproject.toml")
        for base in (root, root / "src"):
            if base.is_dir():
                for init in base.glob("*/__init__.py"):
                    files.update(p for p in init.parent.rglob("*") if p.is_file()
                                 and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo"))
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
        subprocess.run([
            sys.executable, "-m", "freemocap_sdk.bundle", "--entrypoint", str(BACKEND / "desktop_entry.py"),
            "--name", NAME, "--output", str(OUTPUT), "--work", str(WORK),
            "--add-data", f"{BACKEND / 'skellyclicker_app/workers/train_dlc.py'}:skellyclicker_app/workers",
            "--collect-data", "skellyclicker_app", "--collect-data", "skellyforge", "--collect-data", "freemocap_sdk",
        ], cwd=ROOT, check=True)
        inventory = bundle_inventory()
        if not inventory or source_digest() != inputs:
            raise RuntimeError("Backend build incomplete or inputs changed during the build. Run again.")
        pending = state_file.with_suffix(".tmp")
        pending.write_text(json.dumps({"inputs": inputs, "bundle": inventory}), encoding="utf-8")
        pending.replace(state_file)


if __name__ == "__main__":
    prepare(force="--force" in sys.argv[1:])
