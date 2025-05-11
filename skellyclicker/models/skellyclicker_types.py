
from numpydantic import NDArray, Shape
import numpy as np

PointNameString = str
VideoNameString = str
VideoPathString = str
ClickDataCSVPathString = str

FrameNumberInt = int
ImageNumpyArray = NDArray[Shape["* width, * height, * color_channels"], np.uint8]
