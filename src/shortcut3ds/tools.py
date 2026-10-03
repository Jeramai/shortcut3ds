import os
import shutil
from importlib import resources
from pathlib import Path

from shortcut3ds import setup


class ToolError(Exception):
    pass


def find(name: str) -> Path:
    env = os.environ.get(f"SHORTCUT3DS_{name.upper()}")
    if env:
        return Path(env)
    found = shutil.which(name)
    if found:
        return Path(found)
    if (setup.tools_dir() / name).is_file():
        return setup.tools_dir() / name
    raise ToolError(f"{name} not found. Run `shortcut3ds setup`, or put it on PATH.")


def stub_elf() -> Path:
    path = Path(str(resources.files("shortcut3ds") / "data" / "stub.elf"))
    if not path.is_file():
        raise ToolError("data/stub.elf is missing. Build it with `make stub`.")
    return path
