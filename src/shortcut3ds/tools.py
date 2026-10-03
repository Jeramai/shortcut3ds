import os
import shutil
from importlib import resources
from pathlib import Path

REPO_TOOLS = Path(__file__).resolve().parents[2] / ".tools"


class ToolError(Exception):
    pass


def find(name: str) -> Path:
    env = os.environ.get(f"SHORTCUT3DS_{name.upper()}")
    if env:
        return Path(env)
    found = shutil.which(name)
    if found:
        return Path(found)
    local = REPO_TOOLS / name
    if local.is_file():
        return local
    raise ToolError(f"{name} not found. Put it on PATH or set SHORTCUT3DS_{name.upper()}.")


def stub_elf() -> Path:
    path = Path(str(resources.files("shortcut3ds") / "data" / "stub.elf"))
    if not path.is_file():
        raise ToolError("data/stub.elf is missing. Build it with `make stub`.")
    return path
