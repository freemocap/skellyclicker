
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