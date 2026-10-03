import re

from PIL import Image

from shortcut3ds import cia

DEFAULT_ICON_COLOUR = (70, 90, 160)


def safe_name(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-") or "shortcut"


def parse_unique_id(value: str | None) -> int | None:
    if not value:
        return None
    uid = int(value, 16)
    if not cia.UNIQUE_ID_FIRST <= uid < cia.UNIQUE_ID_FIRST + cia.UNIQUE_ID_COUNT:
        raise ValueError(f"unique id {value} is outside the homebrew range F8000-FEFFF")
    return uid


def load_icon(path: str | None) -> Image.Image | None:
    if not path:
        return None
    img = Image.open(path).convert("RGBA")
    flat = Image.new("RGB", img.size, (255, 255, 255))
    flat.paste(img, mask=img)
    return flat


def placeholder_icon() -> Image.Image:
    return Image.new("RGB", (48, 48), DEFAULT_ICON_COLOUR)
