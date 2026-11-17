"""Frozen desktop entry point; the SDK owns readiness and parent-bound lifetime."""
import os
from pathlib import Path
import sys

from freemocap_sdk.desktop import run_desktop_server
from skellyclicker_app.app import build_app
from skellyclicker_app.gpu_runtime import gpu_command

if __name__ == "__main__":
    tools = Path(sys.executable).parent / "tools"
    if getattr(sys, "frozen", False) and tools.is_dir():
        os.environ["PATH"] = os.pathsep.join((str(tools), os.environ.get("PATH", "")))
    if not gpu_command(sys.argv[1:]):
        run_desktop_server(build_app())
