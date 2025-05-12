import logging

from fastapi import APIRouter, WebSocket

from skellyclicker.api.websocket.websocket_server import SkellyClickerWebsocketServer

logger = logging.getLogger(__name__)

websocket_router = APIRouter()


@websocket_router.websocket("/connect")
async def websocket_server_connect(websocket: WebSocket):
    """
    Websocket endpoint for client connection to the server - handles image data streaming to frontend.
    """

    await websocket.accept()
    logger.success(f"SkellyClicker Websocket connection established")

    async with SkellyClickerWebsocketServer(websocket=websocket) as runner:
        await runner.run()
    logger.info("Websocket closed")
