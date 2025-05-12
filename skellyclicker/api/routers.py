from skellyclicker.api.http.app.health import health_router
from skellyclicker.api.http.app.state import state_router
from skellyclicker.api.http.session.recording_router import session_router
from skellyclicker.api.http.videos.videos_router import videos_router
from skellyclicker.api.websocket.websocket_connect import websocket_router

SKELLYCLICKER_ROUTERS = {
    "/app": {
        "health": health_router,
        "state": state_router,
    },
    "/videos": {
        "videos": videos_router,
    },
    "/session": {
        "session": session_router,
    },
    "/websocket": {
        "connect": websocket_router,
    },
}
