from skellyclicker.api.http.app.health import health_router
from skellyclicker.api.http.app.state import state_router
from skellyclicker.api.http.session.session_router import session_router

SKELLYCLICKER_ROUTERS = {
    "/app": {
        "health": health_router,
        "state": state_router,
    },

    "/session": {
        "session": session_router,
    }
}
