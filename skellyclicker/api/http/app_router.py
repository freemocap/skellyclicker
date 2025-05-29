import logging
import os
import signal

from fastapi import APIRouter

from skellyclicker.app.skellyclicker_app import get_skellyclicker_app

HELLO_FROM_SKELLYCLICKER_BACKEND_MESSAGE = {"message": "Hello from the SkellyClicker Backend 💀👆✨"}

logger = logging.getLogger(__name__)

app_router = APIRouter(
    prefix="/app",
    tags=["app"],
    responses={404: {"description": "Not found"}},
)

@app_router.get("/health", summary="Hello👋")
def healthcheck_endpoint():
    """
    A simple endpoint to greet the user of the SkellyClicker API.

    This can be used as a sanity check to ensure the API is responding.
    """
    logger.api("Hello requested! Deploying Hello!")
    return HELLO_FROM_SKELLYCLICKER_BACKEND_MESSAGE

@app_router.get("/state", summary="State of the SkellyClicker app")
def get_app_state():
    """
    Endpoint to retrieve the current state of the SkellyClicker application.

    This can be used to check the status of the application and its components.
    """
    logger.api("App state requested")
    app = get_skellyclicker_app()
    state = app.get_app_state().model_dump_json()
    logger.api(f"Current app state: {state}")
    return {"state": state}

@app_router.get("/shutdown", summary="goodbye👋")
def shutdown_server():
    """
    Endpoint to gracefully shut down the server.

    This is useful for controlled shutdowns, such as during deployments or maintenance.
    """
    logger.api("Server shutdown complete - Killing process... Bye!👋")
    os.kill(os.getpid(), signal.SIGINT)