import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from skellyclicker.api.server.server_constants import APP_URL

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.api(f"SkellyClicker API starting (app: {app})...")
    # logger.info(f"SkellyClicker API base folder path: {get_skellyclicker_base_data_folder_path()}")
    # Path(get_skellyclicker_base_data_folder_path()).mkdir(parents=True, exist_ok=True)

    localhost_url = APP_URL.replace('0.0.0.0', 'localhost')
    logger.success(f"SkellyClicker API started successfully 💀🤖💬")
    logger.api(
        f"SkellyClicker API  running on: \n\t\t\tSwagger API docs - {localhost_url}")# \n\t\t\tTest UI: {localhost_url}/ui 👈[click to open backend UI in your browser]")

    # Let the app do its thing
    yield

    # Shutdown actions
    logger.api("SkellyClicker API ending...")
    logger.success("SkellyClicker API shutdown complete - Goodbye!👋")
