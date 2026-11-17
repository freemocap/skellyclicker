"""Provision and locate the isolated interpreters used by GPU jobs."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import threading

PACKAGE = Path(__file__).parent
WORKERS = ("zed", "pose", "training")
MODEL_REVISION = "7f3c15896eeed50a3f024260543525c6f1d036f4"
BACKBONE_REVISION = "b5b1dcfc1a526af275ec440b8d697c66c90a98b1"
_launch_lock = threading.Lock()


def runtime_root():
    override = os.environ.get("SKELLYCLICKER_GPU_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return data / "SkellyClicker" / "gpu"


def interpreter(venv):
    return str(venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))


def dev_training_root():
    project = PACKAGE / "gpu" / "training"
    digest = hashlib.sha256((project / "uv.lock").read_bytes() + BACKBONE_REVISION.encode())
    return runtime_root() / ("dev-dlc-" + digest.hexdigest()[:16])


def training_python():
    override = os.environ.get("SKELLYCLICKER_TRAINING_PYTHON")
    if override and Path(override).is_file():
        return override
    dev = interpreter(dev_training_root() / "training")
    installed = runtime_config()["training_python"]
    candidates = (dev, installed) if os.environ.get("SKELLYCLICKER_DEV_ORIGIN") else (installed, dev)
    return next((path for path in candidates if Path(path).is_file()), "")


def prepare_dev_training():
    if sys.platform not in ("win32", "linux") or platform.machine().lower() not in ("amd64", "x86_64"):
        print("Local CUDA training is available on Windows and Linux x64.", flush=True)
        return
    root = dev_training_root()
    project = PACKAGE / "gpu" / "training"
    print("Preparing DeepLabCut training environment…", flush=True)
    sync_worker(project, root / "training", "uv")
    cache_training_model(root)
    print("DeepLabCut training environment ready.", flush=True)


def sdk_root():
    default = "C:/Program Files (x86)/ZED SDK" if os.name == "nt" else "/usr/local/zed"
    return Path(os.environ.get("ZED_SDK_ROOT_DIR", default))


def config_for(directory):
    dlls = []
    if os.name == "nt":
        dlls.append(os.environ.get("SKELLYCLICKER_ZED_SDK_BIN", str(sdk_root() / "bin")))
        if os.environ.get("CUDA_PATH"):
            dlls.append(str(Path(os.environ["CUDA_PATH"]) / "bin"))
    return {
        **{name + "_python": interpreter(directory / name) for name in WORKERS},
        "zed_dlls": dlls,
        "pose_dlls": os.environ.get("SKELLYCLICKER_POSE_DLLS", ""),
        "pose_models": str(directory / "models"),
    }


def runtime_config():
    root = runtime_root()
    active = root / "active.json"
    if active.is_file():
        generation = json.loads(active.read_text(encoding="utf-8"))["generation"]
        return config_for(root / generation)
    # Keep existing standalone worker setups usable before provisioning.
    base = Path(os.environ.get("SKELLYCLICKER_ZED_RUNTIME", Path.home() / "AppData/Local/ZEDBenchy"))
    config = config_for(base)
    config.update(zed_python=interpreter(base / ".venv"), pose_python=interpreter(base / "pose-env"),
                  training_python=interpreter(Path.home() / "freemocap_data/training_environments/benchy-dlc"))
    config.pop("pose_models")
    if os.name == "nt":
        config["zed_dlls"] += sorted({str(p.parent) for p in (base / "cuda12-runtime").rglob("cudart64_12.dll")})
        legacy_lib = Path.home() / "code-stuff/codeberg/jonmatthis/playground/happypose/local_data/windows-env/Lib/site-packages/torch/lib"
        if legacy_lib.is_dir() and not config["pose_dlls"]:
            config["pose_dlls"] = str(legacy_lib)
    return config


def launch_external(args, *, extra_env=None, **kwargs):
    """Restore the host loader environment for workers launched by PyInstaller."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI") and
           k not in ("_MEIPASS2", "PYTHONHOME", "PYTHONPATH")}
    if hasattr(sys, "_MEIPASS"):
        original = env.pop("LD_LIBRARY_PATH_ORIG", None)
        env.pop("LD_LIBRARY_PATH", None)
        if original:
            env["LD_LIBRARY_PATH"] = original
    env.update(extra_env or {})
    kwargs.setdefault("stdin", subprocess.DEVNULL)
    kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if os.name != "nt" or not hasattr(sys, "_MEIPASS"):
        return subprocess.Popen(args, env=env, **kwargs)
    import ctypes
    with _launch_lock:
        ctypes.windll.kernel32.SetDllDirectoryW(None)
        try:
            return subprocess.Popen(args, env=env, **kwargs)
        finally:
            ctypes.windll.kernel32.SetDllDirectoryW(str(sys._MEIPASS))


def run_external(args, **kwargs):
    with launch_external(args, **kwargs) as child:
        if child.wait():
            raise subprocess.CalledProcessError(child.returncode, args)


def check_workers(config):
    """Exercise the real ZED API, pose model sessions and CUDA training backend."""
    with tempfile.TemporaryDirectory() as scratch:
        request = Path(scratch) / "check.json"
        request.write_text(json.dumps({"runtime": config, "check": True}), encoding="utf-8")
        for name, script in (("zed", "zed_replay.worker"), ("pose", "fit_pose.worker")):
            run_external([config[name + "_python"], str(PACKAGE / "workers" / script), str(request)])
    run_external([config["training_python"], str(PACKAGE / "workers/train_dlc.py"), "check"])


def provision():
    if sys.platform not in ("win32", "linux") or platform.machine().lower() not in ("amd64", "x86_64"):
        raise RuntimeError("GPU workers support Windows x64 and Ubuntu x64.")
    sdk_library = (Path(os.environ.get("SKELLYCLICKER_ZED_SDK_BIN", sdk_root() / "bin")) / "sl_zed64.dll"
                   if os.name == "nt" else sdk_root() / "lib/libsl_zed.so")
    if not sdk_library.is_file():
        raise RuntimeError(f"Install the ZED SDK 5.5 CUDA 12 variant first. Missing {sdk_library}")
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("Install uv and make its executable available on PATH.")
    root = runtime_root()
    root.mkdir(parents=True, exist_ok=True)
    # Unique generations keep concurrent setup and running jobs isolated.
    generation = Path(tempfile.mkdtemp(prefix="runtime-", dir=root))
    print(f"Preparing isolated workers in {generation}", flush=True)
    try:
        prepare_generation(generation, uv)
        pending = generation / "active.json"
        pending.write_text(json.dumps({"generation": generation.name}), encoding="utf-8")
        pending.replace(root / "active.json")
    except BaseException:
        shutil.rmtree(generation)
        raise
    print(f"Activated GPU workers in {generation}", flush=True)


def prepare_generation(generation, uv):
    for name in WORKERS:
        project = generation / "projects" / name
        project.mkdir(parents=True)
        for filename in ("pyproject.toml", "uv.lock"):
            shutil.copyfile(PACKAGE / "gpu" / name / filename, project / filename)
        sync_worker(project, generation / name, uv)
    config = config_for(generation)
    fetch = str(PACKAGE / "workers/cache_models.worker")
    run_external([config["pose_python"], fetch, "pose", MODEL_REVISION, config["pose_models"]])
    cache_training_model(generation)
    check_workers(config)


def sync_worker(project, environment, uv):
    run_external([uv, "sync", "--locked", "--no-dev", "--python", "3.12.13", "--project", str(project)],
                 extra_env={"UV_PROJECT_ENVIRONMENT": str(environment)})


def cache_training_model(directory):
    run_external([interpreter(directory / "training"), str(PACKAGE / "workers/cache_models.worker"),
                  "training", BACKBONE_REVISION, str(directory / "dlc-model-cache")])


def gpu_command(args):
    if args == ["--provision-gpu"]:
        provision()
    elif args == ["--check-gpu"]:
        config = runtime_config()
        if os.environ.get("SKELLYCLICKER_TRAINING_PYTHON"):
            config["training_python"] = os.environ["SKELLYCLICKER_TRAINING_PYTHON"]
        check_workers(config)
    else:
        return False
    return True


if __name__ == "__main__":
    if sys.argv[1:] != ["--prepare-dev-training"]:
        raise SystemExit("Expected --prepare-dev-training")
    prepare_dev_training()
