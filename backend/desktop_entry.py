"""Frozen desktop entry point; the SDK owns readiness and parent-bound lifetime."""
from freemocap_sdk.desktop import run_desktop_server
from skellyclicker_app.app import build_app

if __name__ == "__main__":
    run_desktop_server(build_app())
