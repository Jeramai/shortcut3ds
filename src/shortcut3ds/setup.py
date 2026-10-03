import hashlib
import io
import os
import platform
import stat
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

MAKEROM_URL = "https://github.com/3DSGuy/Project_CTR/releases/download/makerom-v0.19.0/makerom-v0.19.0-{}.zip"
BANNERTOOL_URL = "https://github.com/Jeramai/shortcut3ds/releases/download/tools-1/bannertool-{}.zip"
MGBA_URL = "https://github.com/Jeramai/shortcut3ds/releases/download/mgba-9146/mgba-3ds-9146.zip"


@dataclass(frozen=True)
class Download:
    url: str
    sha256: str
    member: str


COMMON: dict[str, Download] = {
    "mgba.3dsx": Download(
        MGBA_URL, "6a76bfc7c47d14471b0b1bd055faf9985ba22c56bc391503f9fd776deca66bbe", "mgba.3dsx"
    ),
}

DOWNLOADS: dict[str, dict[str, Download]] = {
    "macos_arm64": {
        "makerom": Download(
            MAKEROM_URL.format("macos_arm64"),
            "ea222647bf362d1aa0d8b7570dc65e7968ce6b3d7b103e9cc815a99698d930e0",
            "makerom",
        ),
        "bannertool": Download(
            BANNERTOOL_URL.format("macos_arm64"),
            "0b088d16fbd1fce8d6374bcddef53e7fe6c78349f24dafe22b45bc94c2f0cf6a",
            "bannertool",
        ),
    },
    "macos_x86_64": {
        "makerom": Download(
            MAKEROM_URL.format("macos_x86_64"),
            "a52563e5549cd2dd84e9b8d1cb0d1fdf15ea9bd0f6241e2e178fe4e4bf3a9277",
            "makerom",
        ),
        "bannertool": Download(
            BANNERTOOL_URL.format("macos_x86_64"),
            "b036a60f51f880d3440686899477586cf05dff3b33562d06b24e7c5f7db7ac35",
            "bannertool",
        ),
    },
    "linux_x86_64": {
        "makerom": Download(
            MAKEROM_URL.format("ubuntu_x86_64"),
            "287b809dec064e0ad597e3d272c49ecb7eed41693d5ee6fef9d8a8aa24c2497e",
            "makerom",
        ),
        "bannertool": Download(
            BANNERTOOL_URL.format("linux_x86_64"),
            "6c5c43e623ed6cd2208878cde8bef7cd646bbf1716820e550dc41047da5cd22c",
            "bannertool",
        ),
    },
    "linux_arm64": {
        "bannertool": Download(
            BANNERTOOL_URL.format("linux_arm64"),
            "d8a3e5e1e20b5b194c54c76221f6716fab97ab8bdebbe7b4f68a0f6a7595131a",
            "bannertool",
        ),
    },
}


class SetupError(Exception):
    pass


def tools_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "shortcut3ds" / "bin"


def current_platform() -> str:
    system = {"darwin": "macos", "linux": "linux"}.get(sys.platform)
    machine = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x86_64", "amd64": "x86_64"}.get(
        platform.machine().lower()
    )
    if not system or not machine:
        raise SetupError(f"No prebuilt tools for {sys.platform}/{platform.machine()}.")
    return f"{system}_{machine}"


def fetch(download: Download, dest: Path) -> None:
    with urllib.request.urlopen(download.url, timeout=60) as response:
        data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != download.sha256:
        raise SetupError(f"{download.url} has SHA-256 {digest}, expected {download.sha256}.")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        dest.write_bytes(z.read(download.member))
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def run(force: bool = False) -> Path:
    plat = current_platform()
    wanted = {**DOWNLOADS.get(plat, {}), **COMMON}
    target = tools_dir()
    target.mkdir(parents=True, exist_ok=True)
    for name in ("makerom", "bannertool", *COMMON):
        dest = target / name
        if dest.exists() and not force:
            print(f"{name}: already in {target}")
            continue
        download = wanted.get(name)
        if download is None:
            print(f"{name}: no prebuilt binary for {plat}. Build it and put it on PATH.")
            continue
        print(f"{name}: downloading {download.url}")
        fetch(download, dest)
    return target
