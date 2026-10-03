import json
import shutil
from pathlib import Path

from shortcut3ds import cia, sources
from shortcut3ds.common import load_icon, parse_unique_id, safe_name
from shortcut3ds.sources.base import AppRef, Look, Request

BASE = Path("/")


def describe() -> str:
    return json.dumps(sources.describe())


def inspect(path: str) -> str:
    file = Path(path)
    source = sources.detect(file)
    defaults = source.defaults(file)
    defaults.icon.save(BASE / "work-icon.png")
    return json.dumps({"source": source.name, "title": defaults.title, "publisher": defaults.publisher})


def prepare(spec_json: str) -> str:
    spec = json.loads(spec_json)
    work = BASE / "work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()

    source = sources.get(spec["source"])
    file = Path(spec["file"])
    options = {}
    for name, value in spec.get("options", {}).items():
        if isinstance(value, dict):
            options[name] = AppRef(
                file=Path(value["file"]) if value.get("file") else None, sd_path=value.get("sd_path")
            )
        elif value:
            options[name] = value
    look = Look(
        title=spec["title"].strip() or file.stem,
        publisher=spec["publisher"].strip(),
        icon=load_icon(spec.get("icon")) or load_icon(str(BASE / "work-icon.png")),
        unique_id=parse_unique_id(spec.get("unique_id")),
    )
    shortcut = sources.build(source, Request(file, spec["target"], spec["mode"], options), look)
    commands = cia.prepare(shortcut, work)
    return json.dumps(
        {
            "commands": commands,
            "filename": f"{safe_name(look.title)}.cia",
            "title_id": f"{shortcut.title_id():016X}",
        }
    )
