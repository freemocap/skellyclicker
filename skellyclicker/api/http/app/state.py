import logging

from fastapi import APIRouter

from skellyclicker.app.app_state_singleton import get_skellyclicker_app_state

logger = logging.getLogger(__name__)
state_router = APIRouter()


@state_router.get("/state", summary="Application State")
def app_state_endpoint():
    """
    A simple endpoint that serves the current state of the application
    """
    logger.api("Serving application state from `app/state` endpoint...")

    return get_skellyclicker_app_state().model_dump()

