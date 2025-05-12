import asyncio
import logging
import multiprocessing
import uuid
from typing import Optional

from pydantic import BaseModel
from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect

from skellyclicker.app.app_state_singleton import get_skellyclicker_app_state, \
    SkellyClickerAppState
from skellyclicker.system.logging_configuration.handlers.websocket_log_queue_handler import get_websocket_log_queue

logger = logging.getLogger(__name__)

class SkellyClickerWebsocketServer:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.websocket_queue = get_websocket_log_queue()

    async def __aenter__(self):
        logger.debug("Entering SkellyClicker  WebsocketServer context manager...")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug(" SkellyClicker  WebsocketServer context manager exiting...")
        if not self.websocket.client_state == WebSocketState.DISCONNECTED:
            await self.websocket.close()

    async def run(self):
        logger.info("Starting websocket runner...")
        try:
            await asyncio.gather(
                asyncio.create_task(self._websocket_queue_relay()),
            )
        except Exception as e:
            logger.exception(f"Error in websocket runner: {e.__class__}: {e}")
            raise

    async def _websocket_queue_relay(self):
        """
        Relay messages from the sub-processes to the frontend via the websocket.
        """
        logger.info("Websocket relay listener started...")

        try:
            while True:
                if self.websocket_queue.qsize() > 0:
                    try:
                        message = self.websocket_queue.get()
                        logger.info(f"Got message from queue: {message}")
                        await self.websocket.send_json(message)

                    except multiprocessing.queues.Empty:
                        continue
                else:
                    await asyncio.sleep(1)

        except WebSocketDisconnect:
            logger.api("Client disconnected, ending listener task...")
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("Ending listener for frontend payload messages in queue...")
        logger.info("Ending listener for client messages...")
