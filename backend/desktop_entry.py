"""Frozen desktop entry point; the SDK owns readiness and parent-bound lifetime."""
import os
from pathlib import Path
import sys

from freemocap_sdk.desktop import run_desktop_server
from skellyclicker_app.app import build_app

if __name__ == "__main__":
    tools = Path(sys.executable).parent / "tools"
    if getattr(sys, "frozen", False) and tools.is_dir():
        os.environ["PATH"] = os.pathsep.join((str(tools), os.environ.get("PATH", "")))
    run_desktop_server(build_app())
