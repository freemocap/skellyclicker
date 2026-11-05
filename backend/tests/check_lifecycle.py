"""Exercise the actual SDK runner and graceful signal shutdown in a child process."""
import os
from pathlib import Path
import socket
import subprocess
import sys

with socket.socket() as probe:
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]

program = r'''
import json, signal, threading, time, urllib.request
from skellyclicker_app.app import build_app
from freemocap_sdk.server import run_server
import os
port = int(os.environ["SKELLYCLICKER_TEST_PORT"])
verified = threading.Event()
def check_and_stop():
    try:
        for attempt in range(100):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1) as response:
                    assert json.load(response)["application"] == "skellyclicker"
                verified.set()
                break
            except OSError:
                time.sleep(.1)
    finally:
        signal.raise_signal(signal.SIGINT)
thread = threading.Thread(target=check_and_stop, daemon=True)
thread.start()
try:
    run_server(build_app(), host="127.0.0.1", port=port)
except KeyboardInterrupt:
    pass
thread.join(timeout=2)
assert verified.is_set(), "Backend never became ready"
'''
result = subprocess.run(
    [sys.executable, "-B", "-c", program],
    cwd=Path(__file__).resolve().parents[1],
    env={**os.environ, "SKELLYCLICKER_TEST_PORT": str(port)},
    capture_output=True, text=True, timeout=20,
)
assert result.returncode == 0, result.stdout + result.stderr
assert "Application startup complete" in result.stderr, result.stderr
assert "Application shutdown complete" in result.stderr, result.stderr
with socket.socket() as probe:
    probe.bind(("127.0.0.1", port))
print("PASS: actual SDK runner starts, serves app HTTP, completes signal shutdown, and releases its port")
