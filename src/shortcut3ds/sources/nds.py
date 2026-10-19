import struct
from pathlib import Path

from PIL import Image

from shortcut3ds import cia
from shortcut3ds.common import header_title, placeholder_icon
from shortcut3ds.sources.base import SHORTCUT, Defaults, Look, Request, Source

HEADER_SIZE = 0x160
HEADER_CRC_OFFSET = 0x15E
BANNER_POINTER = 0x68
ICON_OFFSET, PALETTE_OFFSET, ENGLISH_TITLE_OFFSET = 0x20, 0x220, 0x340
BANNER_SIZE = 0x840


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def is_nds_rom(path: Path) -> bool:
    with path.open("rb") as f:
        header = f.read(HEADER_SIZE)
    if len(header) < HEADER_SIZE:
        return False
    (stored,) = struct.unpack_from("<H", header, HEADER_CRC_OFFSET)
    return crc16(header[:HEADER_CRC_OFFSET]) == stored


def read_banner(path: Path) -> bytes | None:
    with path.open("rb") as f:
        f.seek(BANNER_POINTER)
        (offset,) = struct.unpack("<I", f.read(4))
        if not offset:
            return None
        f.seek(offset)
        banner = f.read(BANNER_SIZE)
    return banner if len(banner) == BANNER_SIZE else None


def banner_icon(banner: bytes) -> Image.Image:
    palette = [
        tuple((c >> shift & 0x1F) * 255 // 31 for shift in (0, 5, 10))
        for c in struct.unpack_from("<16H", banner, PALETTE_OFFSET)
    ]
    img = Image.new("RGB", (32, 32), (255, 255, 255))
    px = img.load()
    for y in range(32):
        for x in range(32):
            tile = (y // 8) * 4 + x // 8
            byte = banner[ICON_OFFSET + tile * 32 + (y % 8) * 4 + (x % 8) // 2]
            index = byte >> 4 if x % 2 else byte & 0xF
            # Colour 0 is transparent.
            if index:
                px[x, y] = palette[index]
    return img.resize((48, 48), Image.LANCZOS)


def banner_lines(banner: bytes) -> list[str]:
    raw = banner[ENGLISH_TITLE_OFFSET : ENGLISH_TITLE_OFFSET + 0x100]
    text = raw.decode("utf-16-le", "replace").split("\0", 1)[0]
    return [line.strip() for line in text.split("\n") if line.strip()]


class Nds(Source):
    name = "nds"
    label = "Nintendo DS ROM, opens in nds-bootstrap"
    extensions = (".nds",)
    sd_folder = "/roms/nds"
    modes = (SHORTCUT,)
    notes = (
        "Install YANBF's bootstrap.cia once, and copy the DS Game Forwarder pack to the card.",
        "Keep the ROM at the same path on the card.",
    )

    def matches(self, path: Path) -> bool:
        return is_nds_rom(path)

    def defaults(self, path: Path) -> Defaults:
        banner = read_banner(path)
        lines = banner_lines(banner) if banner else []
        title = " ".join(lines[:-1] if len(lines) > 1 else lines) or header_title(path, 0) or path.stem
        return Defaults(
            title=title,
            publisher=lines[-1] if len(lines) > 1 else "Nintendo DS",
            icon=banner_icon(banner) if banner else placeholder_icon(),
        )

    def shortcut(self, request: Request, look: Look) -> cia.Shortcut:
        return cia.Shortcut(
            target=request.target,
            title=look.title,
            publisher=look.publisher,
            icon=look.icon,
            unique_id=look.unique_id,
            nds=True,
        )
