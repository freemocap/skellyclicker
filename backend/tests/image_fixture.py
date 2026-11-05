"""Produce a real JPEG inside the SDK's self-describing image frame, without files."""
import base64
import io
import json
from PIL import Image
from freemocap_sdk.stream import PayloadImage, encode_image_payload, encode_frame_message, uncalibrated_camera

jpeg = io.BytesIO()
Image.new("RGB", (16, 12), (40, 160, 200)).save(jpeg, format="JPEG", quality=95)
source = jpeg.getvalue()
payload = encode_image_payload(7, [PayloadImage("fixture", 0, 16, 12, source)])
frame = encode_frame_message(frame_number=7, timestamp=1.25, cameras=[uncalibrated_camera("fixture", 0, (16, 12))], image=payload)
print(json.dumps({"frame": base64.b64encode(frame).decode(), "jpeg": base64.b64encode(source).decode()}))
