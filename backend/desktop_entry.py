"""Frozen desktop entry point; the SDK owns readiness and parent-bound lifetime."""
import os
from pathlib import Path
import sys

from time import perf_counter

if __name__ == "__main__":
    started = perf_counter()
    print("Backend Python entry point reached", file=sys.stderr, flush=True)
    from skellyclicker_app.gpu_runtime import gpu_command

    tools = Path(sys.executable).parent / "tools"
    if getattr(sys, "frozen", False) and tools.is_dir():
        os.environ["PATH"] = os.pathsep.join((str(tools), os.environ.get("PATH", "")))
    if not gpu_command(sys.argv[1:]):
        from freemocap_sdk.desktop import run_desktop_server
        from skellyclicker_app.app import build_app

        imported = perf_counter()
        print(f"Backend imports took {imported - started:.2f}s", file=sys.stderr, flush=True)
        app = build_app()
        print(f"Backend app construction took {perf_counter() - imported:.2f}s; starting HTTP server",
              file=sys.stderr, flush=True)
        run_desktop_server(app)
