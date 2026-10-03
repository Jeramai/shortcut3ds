import struct
from dataclasses import dataclass

from PIL import Image

SMDH_SIZE = 0x36C0
TITLES_OFFSET = 0x8
TITLE_SIZE = 0x200
ENGLISH = 1
SMALL_ICON_OFFSET = 0x2040
LARGE_ICON_OFFSET = 0x24C0


@dataclass
class Smdh:
    raw: bytes
    short_title: str
    long_title: str
    publisher: str
    icon: Image.Image


def _utf16(raw: bytes) -> str:
    return raw.decode("utf-16-le").split("\0", 1)[0].strip()


def _morton(i: int) -> tuple[int, int]:
    x = (i & 1) | ((i >> 1) & 2) | ((i >> 2) & 4)
    y = ((i >> 1) & 1) | ((i >> 2) & 2) | ((i >> 3) & 4)
    return x, y


def decode_icon(raw: bytes, size: int) -> Image.Image:
    img = Image.new("RGB", (size, size))
    px = img.load()
    i = 0
    for ty in range(0, size, 8):
        for tx in range(0, size, 8):
            for k in range(64):
                (v,) = struct.unpack_from("<H", raw, i * 2)
                i += 1
                x, y = _morton(k)
                r, g, b = (v >> 11) & 0x1F, (v >> 5) & 0x3F, v & 0x1F
                px[tx + x, ty + y] = (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2)
    return img


def parse(raw: bytes) -> Smdh:
    if raw[:4] != b"SMDH" or len(raw) < SMDH_SIZE:
        raise ValueError("not an SMDH")
    entry = TITLES_OFFSET + ENGLISH * TITLE_SIZE
    return Smdh(
        raw=raw[:SMDH_SIZE],
        short_title=_utf16(raw[entry : entry + 0x80]),
        long_title=_utf16(raw[entry + 0x80 : entry + 0x180]),
        publisher=_utf16(raw[entry + 0x180 : entry + 0x200]),
        icon=decode_icon(raw[LARGE_ICON_OFFSET:], 48),
    )
