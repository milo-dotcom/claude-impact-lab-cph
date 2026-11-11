"""claims.image_block: a big phone photo must reach the API as a small, upright JPEG.

    .venv/bin/python tests/test_image_block.py
"""
import base64
import io
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import claims  # noqa: E402

# 50 MP-ish noise photo, saved as PNG: far over the API's 5 MB image limit.
raw = io.BytesIO()
Image.frombytes("RGB", (6000, 4000), os.urandom(6000 * 4000 * 3)).save(raw, "PNG", compress_level=1)
assert raw.tell() > 5_000_000

block = claims.image_block(raw.getvalue())
jpeg = base64.b64decode(block["source"]["data"])
img = Image.open(io.BytesIO(jpeg))
assert block["source"]["media_type"] == "image/jpeg" and img.format == "JPEG"
assert max(img.size) == claims.MAX_IMAGE_SIDE and img.size[0] > img.size[1]
assert len(block["source"]["data"]) < 5_000_000

# Phone held upright: pixels stored landscape, EXIF orientation 6 says "rotate 90°".
rot = io.BytesIO()
exif = Image.Exif()
exif[0x0112] = 6
Image.new("RGB", (400, 300)).save(rot, "JPEG", exif=exif)
w, h = Image.open(io.BytesIO(base64.b64decode(claims.image_block(rot.getvalue())["source"]["data"]))).size
assert (w, h) == (300, 400)

try:
    claims.image_block(b"not an image")
    raise AssertionError("garbage bytes should raise")
except ValueError:
    pass

print("ok")
