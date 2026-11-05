import time
from fastapi import APIRouter
from freemocap_sdk.server import Connection, create_app

router = APIRouter(prefix="/api")


@router.get("/status")
async def status():
    return {"application": "skellyclicker", "mode": "playback", "recording": None}


async def stream_updates(connection: Connection):
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
    return create_app(
        title="SkellyClicker",
        routers=(router,),
        allowed_origins=("http://127.0.0.1:5176", "http://localhost:5176", "http://tauri.localhost", "tauri://localhost"),
        websocket_handler=stream_updates,
    )
