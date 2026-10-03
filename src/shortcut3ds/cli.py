import argparse
import re
import shutil
import sys
from pathlib import Path

from PIL import Image

from shortcut3ds import __version__, cia, smdh, threedsx, tools

DEFAULT_ICON = smdh.Smdh(
    raw=b"", short_title="", long_title="", publisher="", icon=Image.new("RGB", (48, 48), (70, 90, 160))
)


def sd_root_of(path: Path) -> Path | None:
    parts = path.resolve().parts
    if len(parts) >= 3 and parts[1] == "Volumes":
        return Path(*parts[:3])
    for parent in path.resolve().parents:
        if (parent / "Nintendo 3DS").is_dir():
            return parent
    return None


def sd_target(app: Path, sd: Path | None) -> tuple[str, Path | None]:
    root = sd or sd_root_of(app)
    if root is None:
        raise SystemExit("Cannot tell where the SD card starts. Pass --sd or --target.")
    try:
        rel = app.resolve().relative_to(root.resolve())
    except ValueError:
        raise SystemExit(f"{app} is not on the SD card at {root}.")
    return "/" + rel.as_posix(), root


def safe_name(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-") or "shortcut"


def cmd_make(a: argparse.Namespace) -> int:
    app = Path(a.app)
    if not app.is_file():
        raise SystemExit(f"{app} does not exist.")
    if a.target:
        target, root = a.target, a.sd
    else:
        target, root = sd_target(app, a.sd)

    raw = threedsx.read_smdh(app)
    info = smdh.parse(raw) if raw else DEFAULT_ICON
    title = a.title or info.short_title or app.stem
    shortcut = cia.Shortcut(
        target=target,
        title=title,
        publisher=a.publisher or info.publisher,
        icon_smdh=info,
        args=tuple(a.arg),
        unique_id=int(a.unique_id, 16) if a.unique_id else None,
    )

    out = Path(a.output) if a.output else Path.cwd() / f"{safe_name(title)}.cia"
    cia.build(shortcut, out)
    print(f"Built {out}")
    print(f"  title    {title}")
    print(f"  target   sdmc:{target}")
    print(f"  title id {shortcut.title_id():016X}")

    if a.install:
        if root is None:
            raise SystemExit("--install needs the SD card. Pass --sd.")
        dest = Path(root) / "cia" / out.name
        dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(out, dest)
        print(f"Copied to {dest}. Install it with FBI: SD > cia > {out.name}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="shortcut3ds", description="Make HOME Menu shortcuts for 3DS homebrew.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    m = sub.add_parser("make", help="make a CIA that opens a .3dsx from the HOME Menu")
    m.add_argument("app", help="the .3dsx file, ideally on the mounted SD card")
    m.add_argument("--sd", type=Path, help="SD card root (found from the app path when possible)")
    m.add_argument("--target", help="SD path of the .3dsx, e.g. /3ds/app/app.3dsx")
    m.add_argument("--title", help="name on the HOME Menu (default: the app's own)")
    m.add_argument("--publisher", help="publisher line (default: the app's own)")
    m.add_argument("--arg", action="append", default=[], help="extra argument for the app; repeatable")
    m.add_argument("--unique-id", help="hex unique id in F8000-FEFFF (default: from the path)")
    m.add_argument("-o", "--output", help="where to write the .cia")
    m.add_argument("--install", action="store_true", help="also copy the .cia to SD:/cia")
    m.set_defaults(func=cmd_make)

    a = p.parse_args(argv)
    try:
        return a.func(a)
    except (tools.ToolError, threedsx.ThreeDsxError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
