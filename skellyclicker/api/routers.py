from skellyclicker.api.http.data_router import data_router
from skellyclicker.api.http.video_router import video_router
from skellyclicker.api.http.app_router import app_router


SKELLYCLICKER_ROUTERS = {
    "app": app_router,
    "video": video_router,
    "data": data_router,
}