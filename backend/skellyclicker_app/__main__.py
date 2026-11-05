import argparse
import os

from freemocap_sdk.server import run_server
from .app import build_app


def main():
    parser = argparse.ArgumentParser(description="Run the SkellyClicker playback backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("SKELLYCLICKER_PORT", "8006")))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    run_server(build_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
