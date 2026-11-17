"""Install one release package on a disposable CI host and exercise its payload."""

import argparse
import hashlib
import json
import os
import queue
import re
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path


def run(*args, timeout=60, **kwargs):
    return subprocess.run(args, check=True, timeout=timeout, text=True, **kwargs)


def single(paths, description):
    matches = list(paths)
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {description}, found {matches}")
    return matches[0]


def install(folder, work):
    extension = {"linux": "deb", "darwin": "dmg", "win32": "exe"}[sys.platform]
    installer = single(folder.glob(f"*.{extension}"), "native installer").resolve()
    with installer.open("rb") as handle:
        print(f"Testing {installer.name} sha256={hashlib.file_digest(handle, 'sha256').hexdigest()}", flush=True)
    if sys.platform == "linux":
        run("sudo", "apt-get", "update", timeout=300)
        run("sudo", "apt-get", "install", "-y", str(installer), timeout=600)
        package = run("dpkg-deb", "-f", installer, "Package", capture_output=True).stdout.strip()
        files = run("dpkg-query", "-L", package, capture_output=True).stdout.splitlines()
        return single((Path(name) for name in files if name.endswith("/backend/skellyclicker-backend")),
                      "installed DEB backend")
    if sys.platform == "darwin":
        mount = work / "volume"
        mount.mkdir()
        run("hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", mount, installer)
        app = work / "installed" / "SkellyClicker.app"
        try:
            app.parent.mkdir()
            run("ditto", mount / app.name, app, timeout=300)
        finally:
            run("hdiutil", "detach", mount)
        return app / "Contents" / "Resources" / "backend" / "skellyclicker-backend"

    # NSIS requires an unquoted /D=... as the last raw argument, including spaces.
    destination = work / "installed"
    command = subprocess.list2cmdline([str(installer), "/S"]) + f" /D={destination}"
    subprocess.run(command, executable=str(installer), check=True, timeout=600)
    return destination / "backend" / "skellyclicker-backend.exe"


def smoke_tools(backend, work):
    tools = backend.parent / "tools"
    ext = backend.suffix
    run(tools / ("node" + ext), "--version")
    video = work / "test.mp4"
    run(tools / ("ffmpeg" + ext), "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
        "color=size=16x16:rate=2", "-frames:v", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", video)
    probe = run(tools / ("ffprobe" + ext), "-v", "error", "-select_streams", "v:0", "-count_frames",
                "-show_entries", "stream=codec_name,nb_read_frames", "-of", "json", video, capture_output=True)
    stream = single(json.loads(probe.stdout)["streams"], "probe stream")
    if stream["codec_name"] != "h264" or int(stream["nb_read_frames"]) != 2:
        raise RuntimeError(f"Bundled media round trip failed: {stream}")


def read_ready(stdout, events):
    for line in stdout:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and record.get("event") == "freemocap_ready":
            events.put(record)
    events.put(None)


def smoke_backend(backend, work):
    env = {**os.environ, "SKELLYLOGS_LOG_DIR": str(work / "logs"),
           "SKELLYCLICKER_SESSION_PATH": str(work / "session.json")}
    child = subprocess.Popen([backend], cwd=work, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             env=env, text=True, encoding="utf-8", errors="replace")
    with child:
        try:
            ready = queue.Queue()
            threading.Thread(target=read_ready, args=(child.stdout, ready), daemon=True).start()
            try:
                event = ready.get(timeout=90)
            except queue.Empty as error:
                raise RuntimeError("Backend readiness timed out") from error
            if not event or event.get("pid") != child.pid:
                raise RuntimeError(f"Backend closed stdout or announced an unexpected PID: {event}")
            address = re.fullmatch(r"http://127\.0\.0\.1:(\d+)", event["url"])
            if not address or not 0 < int(address[1]) < 65536:
                raise RuntimeError(f"Invalid loopback readiness URL: {event}")
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(event["url"] + "/api/status", timeout=10) as response:
                status = json.load(response)
            if status.get("application") != "skellyclicker" or status.get("mode") != "playback":
                raise RuntimeError(f"Unexpected installed app status: {status}")
            child.stdin.write('{"command":"shutdown"}\n')
            child.stdin.close()
            if child.wait(timeout=20) != 0:
                raise RuntimeError(f"Backend shutdown exited {child.returncode}")
            with socket.socket() as sock:
                sock.settimeout(2)
                if sock.connect_ex(("127.0.0.1", int(address[1]))) == 0:
                    raise RuntimeError("Backend still listens after shutdown")
        finally:
            if child.poll() is None:
                child.kill()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("installer_directory", type=Path, nargs="?")
    group.add_argument("--backend", type=Path, help="Exercise an existing payload, skipping installation")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="skellyclicker-smoke-") as directory:
        work = Path(directory)
        backend = args.backend.resolve() if args.backend else install(args.installer_directory, work)
        print(f"Exercising {backend}", flush=True)
        smoke_backend(backend, work)
        smoke_tools(backend, work)
        print("Passed backend readiness, HTTP status, shutdown, port release, Node, and H.264 tool checks.")


if __name__ == "__main__":
    main()
