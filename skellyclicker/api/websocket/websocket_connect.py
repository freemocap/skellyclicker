import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket

from skellyclicker.api.websocket.websocket_server import SkellyClickerWebsocketServer

logger = logging.getLogger(__name__)

skellyclicker_websocket_router = APIRouter()


def is_valid_uuid(uuid: str) -> bool:
    """
    Check if a string is a valid UUID.
    """
    try:
        uuid_obj = UUID(uuid)
    except ValueError:
        return False
    return str(uuid_obj) == uuid


@skellyclicker_websocket_router.websocket("/connect/{session_id}")
async def skellyclicker_websocket_server_connect(websocket: WebSocket, session_id: str):
    """
    Websocket endpoint for client connection to the server - handles image data streaming to frontend.
    """

    if not is_valid_uuid(session_id):
        logger.error(f"Invalid session_id: {session_id}")
        await websocket.close()
        return
    await websocket.accept()
    logger.success(f"SkellyClicker Websocket connection established for session_id[-5:]: {session_id[-5:]}")

    async with SkellyClickerWebsocketServer(websocket=websocket,
                                         session_id=session_id) as runner:
        await runner.run()
    logger.info("Websocket closed")
