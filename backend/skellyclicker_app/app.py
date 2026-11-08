import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from fastapi import APIRouter, Request
from freemocap_sdk.server import Connection, create_app
from freemocap_sdk.logs import LogHub

from .project_routes import router as project_router
from .preparation import router as preparation_router, shutdown_jobs
from .playback_adapter import router as playback_router
from .label_routes import router as label_router, task_router, registry
from .training_routes import router as training_router
from .session import router as session_router
from .refinement_routes import router as refinement_router
from .quality_routes import router as quality_router
from freemocap_sdk.pipeline import stream_pipeline_snapshots

router = APIRouter(prefix="/api")
logger = logging.getLogger("skellyclicker")

@router.get("/status")
async def status(request: Request):
    return {"application": "skellyclicker", "mode": "playback", "recording": None, "log_session_id": request.app.state.log_session_id}

async def state_updates(connection: Connection):
    sequence = 0
    while True:
        await connection.send_message(
            "skellyclicker_state",
            {"application": "skellyclicker", "mode": "playback", "ready": True},
            timestamp=time.time(), sequence=sequence,
        )
        await connection.receive_json()
        sequence += 1

def build_app():
    hub = LogHub(capacity=1000)

    @asynccontextmanager
    async def lifespan(app):
        previous_level = logger.level
        logger.setLevel(logging.INFO)
        # Uvicorn uses non-propagating loggers; attach once at each owned boundary.
        destinations = [logging.getLogger()]
        destinations.extend(logging.getLogger(name) for name in ("uvicorn", "uvicorn.access")
                            if not logging.getLogger(name).propagate)
        for destination in destinations:
            destination.addHandler(hub)
        logger.info("SkellyClicker backend ready; live logs connected to the SDK terminal")
        try:
            yield
        finally:
            logger.info("SkellyClicker backend shutting down")
            shutdown_jobs()
            for destination in destinations:
                destination.removeHandler(hub)
            logger.setLevel(previous_level)
            hub.close()

    async def stream_updates(connection: Connection):
        tasks = [asyncio.create_task(state_updates(connection)), asyncio.create_task(hub.forward(connection)), asyncio.create_task(stream_pipeline_snapshots(connection,registry))]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    origins = ["http://127.0.0.1:5176", "http://localhost:5176", "http://tauri.localhost", "tauri://localhost"]
    dev_origin = os.environ.get("SKELLYCLICKER_DEV_ORIGIN", "")
    port = dev_origin.removeprefix("http://127.0.0.1:")
    if dev_origin != port and port.isascii() and port.isdecimal() and 0 < int(port) <= 65535:
        origins.append(dev_origin)
    app = create_app(
        title="SkellyClicker",
        routers=(router, project_router, preparation_router, playback_router, label_router, task_router, training_router, session_router, refinement_router, quality_router),
        lifespan=lifespan,
        allowed_origins=tuple(origins),
        websocket_handler=stream_updates,
    )
    app.state.log_session_id = hub.session_id
    return app
