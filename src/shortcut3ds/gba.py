import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FIXED_VALUE_OFFSET = 0xB2
TITLE_OFFSET = 0xA0
ICON_COLOUR = (79, 70, 180)


def is_gba_rom(path: Path) -> bool:
    with path.open("rb") as f:
        header = f.read(0xC0)
    return len(header) == 0xC0 and header[FIXED_VALUE_OFFSET] == 0x96


def title_from_name(path: Path) -> str:
    name = re.sub(r"\s*[\(\[][^)\]]*[\)\]]", "", path.stem)
    return re.sub(r"\s+", " ", name.replace("_", " ")).strip() or header_title(path)


def header_title(path: Path) -> str:
    with path.open("rb") as f:
        f.seek(TITLE_OFFSET)
        return f.read(12).split(b"\0", 1)[0].decode("ascii", "replace").strip().title()


def _initials(title: str) -> str:
    words = [w for w in re.split(r"[\s:-]+", title) if w and w[0].isalnum()]
    skip = {"the", "a", "an", "of", "and", "version"}
    picked = [w for w in words if w.lower() not in skip] or words
    return "".join(w[0] for w in picked[:2]).upper() or "?"


def default_icon(title: str) -> Image.Image:
    img = Image.new("RGB", (48, 48), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, 47, 47], radius=9, fill=ICON_COLOUR)
    draw.text((24, 21), _initials(title), font=ImageFont.load_default(size=20), fill="white", anchor="mm")
    draw.text((24, 39), "GBA", font=ImageFont.load_default(size=9), fill=(205, 200, 255), anchor="mm")
    return img


def find_emulator(sd_root: Path) -> Path | None:
    apps = sd_root / "3ds"
    if not apps.is_dir():
        return None
    # macOS writes "._name" AppleDouble files next to every file on a FAT card.
    found = sorted(p for p in apps.rglob("*.3dsx") if "mgba" in p.name.lower() and not p.name.startswith("."))
    return found[0] if found else None
