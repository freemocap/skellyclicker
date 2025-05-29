from skellyclicker.api.http.app_router import app_router
from skellyclicker.api.http.data_router import data_router
from skellyclicker.api.http.dlc_router.dlc_router import dlc_router
from skellyclicker.api.http.session_router import session_router
from skellyclicker.api.http.video_router import video_router



SKELLYCLICKER_ROUTERS = {
    "app": app_router,
    "session": session_router,
    "video": video_router,
    "data": data_router,
    "dlc": dlc_router,
}