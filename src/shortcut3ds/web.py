import json
import shutil
from pathlib import Path

from PIL import Image

from shortcut3ds import cia, gba
from shortcut3ds.cli import DEFAULT_ICON_COLOUR, app_info, load_icon, parse_unique_id, safe_name

BASE = Path("/")


def inspect(path: str) -> str:
    file = Path(path)
    with file.open("rb") as f:
        magic = f.read(4)
    if magic == b"3DSX":
        info = app_info(file)
        icon = info.icon if info else Image.new("RGB", (48, 48), DEFAULT_ICON_COLOUR)
        icon.save(BASE / "work-icon.png")
        return json.dumps(
            {
                "kind": "3dsx",
                "title": (info and info.short_title) or file.stem,
                "publisher": (info and info.publisher) or "",
            }
        )
    if gba.is_gba_rom(file):
        title = gba.title_from_name(file)
        gba.default_icon(title).save(BASE / "work-icon.png")
        return json.dumps({"kind": "gba", "title": title, "publisher": "Game Boy Advance"})
    raise ValueError("This is not a .3dsx app or a GBA ROM.")


def prepare(spec_json: str) -> str:
    spec = json.loads(spec_json)
    work = BASE / "work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()

    source = Path(spec["file"])
    native = spec["mode"] == "native"
    title = spec["title"].strip() or source.stem
    icon = load_icon(spec.get("icon")) or Image.open(BASE / "work-icon.png")
    shortcut = cia.Shortcut(
        target=spec["target"],
        title=title,
        publisher=spec["publisher"].strip(),
        icon=icon,
        unique_id=parse_unique_id(spec.get("unique_id")),
    )

    if spec["kind"] == "3dsx":
        if native:
            shortcut.embed = source
    else:
        shortcut.id_key = spec["target"]
        if native:
            shortcut.embed = Path(spec["emulator"])
            shortcut.romfs_files = {spec["rom_name"]: source, "filename": spec["rom_name"].encode()}
        else:
            shortcut.target = spec["emulator_target"]
            shortcut.deliver = spec["target"].encode() + b"\0"

    commands = cia.prepare(shortcut, work)
    return json.dumps(
        {
            "commands": commands,
            "filename": f"{safe_name(title)}.cia",
            "title_id": f"{shortcut.title_id():016X}",
        }
    )
