
__url__ = "https://github.com/freemocap/skellyclicker"

import logging
# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

PointNameString = str
VideoNameString = str
VideoPathString = str
ClickDataCSVPathString = str

MAX_WINDOW_SIZE = (1920, 1080)
ZOOM_STEP = 1.1
ZOOM_MIN = 1.0
ZOOM_MAX = 10.0
POSITION_EPSILON = 1e-6  # Small threshold for position changes
