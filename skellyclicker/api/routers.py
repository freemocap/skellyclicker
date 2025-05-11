from skellyclicker.api.http.app.health import health_router
from skellyclicker.api.http.app.state import state_router
from skellyclicker.api.http.session.session_router import session_router
from skellyclicker.api.http.videos.videos_router import videos_router

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
    }
}
