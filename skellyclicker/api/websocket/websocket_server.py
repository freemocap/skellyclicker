import asyncio
import logging
import multiprocessing
import uuid
from typing import Optional

from pydantic import BaseModel
from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect

from skellyclicker.api.http.videos.videos_router import FramesResponse
from skellyclicker.app.app_state_singleton import get_skellyclicker_app_state, \
    SkellyClickerAppState
from skellyclicker.models.video_models import VideoGroupHandler
from skellyclicker.system.logging_configuration.handlers.websocket_log_queue_handler import get_websocket_log_queue

logger = logging.getLogger(__name__)
class FrameRequest(BaseModel):
    type: str = "frame_request"
    frame_number: int

class SkellyClickerWebsocketServer:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket


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
                if get_websocket_log_queue().qsize() > 0:
                    try:
                        message = get_websocket_log_queue().get()
                        # logger.info(f"Got message from queue: {message}")
                        # await self.websocket.send_json(message.model_dump())

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

    async def _listen_for_client_messages(self):

        """
        Listen for messages from the client and handle them.
        """
        logger.info("Listening for client messages...")
        try:
            while True:
                message = await self.websocket.receive_json()
                logger.info(f"Received message from client: {message}")
                # Handle the message here
                if message.get("type") == "frame_request":
                    frame_number = message.get("frame_number")
                    await self.send_frame(frame_number)
                else:
                    logger.warning(f"Unknown message type: {message.get('type')}")
        except WebSocketDisconnect:
            logger.api("Client disconnected, ending listener task...")
        except asyncio.CancelledError:
            pass

    async def send_frame(self, frame_number: int):
        """Send frame data to the client via WebSocket."""
        try:
            video_group_handler: VideoGroupHandler = get_skellyclicker_app_state().video_group_handler
            if not video_group_handler:
                logger.error("No video group handler available")
                return

            images = video_group_handler.get_images_by_frame_number(frame_number=frame_number)
            if not images:
                logger.error(f"No images found for frame number: {frame_number}")
                return

            # Convert images to base64
            frames_response = FramesResponse.from_numpy_images(images=images, frame_number=frame_number)

            # Create WebSocket message
            message = {
                "type": "frame_data",
                "frame_number": frame_number,
                "frames": frames_response.frames
            }

            # Send the message
            await self.websocket.send_json(message)

        except Exception as e:
            logger.exception(f"Error sending frame via WebSocket: {e}")