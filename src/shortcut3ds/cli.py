import argparse
import re
import shutil
import sys
from pathlib import Path

from PIL import Image

from shortcut3ds import __version__, cia, gba, setup, smdh, threedsx, tools

DEFAULT_ICON_COLOUR = (70, 90, 160)


def sd_root_of(path: Path) -> Path | None:
    parts = path.resolve().parts
    if len(parts) >= 3 and parts[1] == "Volumes":
        return Path(*parts[:3])
    for parent in path.resolve().parents:
        if (parent / "Nintendo 3DS").is_dir():
            return parent
    return None


def sd_target(file: Path, sd: Path | None) -> tuple[str, Path]:
    root = sd or sd_root_of(file)
    if root is None:
        raise SystemExit("Cannot tell where the SD card starts. Pass --sd or --target.")
    try:
        rel = file.resolve().relative_to(root.resolve())
    except ValueError:
        raise SystemExit(f"{file} is not on the SD card at {root}.") from None
    return "/" + rel.as_posix(), root


def safe_name(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-") or "shortcut"


def parse_unique_id(value: str | None) -> int | None:
    if not value:
        return None
    uid = int(value, 16)
    if not cia.UNIQUE_ID_FIRST <= uid < cia.UNIQUE_ID_FIRST + cia.UNIQUE_ID_COUNT:
        raise ValueError(f"--unique-id {value} is outside the homebrew range F8000-FEFFF")
    return uid


def load_icon(path: str | None) -> Image.Image | None:
    if not path:
        return None
    img = Image.open(path).convert("RGBA")
    flat = Image.new("RGB", img.size, (255, 255, 255))
    flat.paste(img, mask=img)
    return flat


def build_and_report(shortcut: cia.Shortcut, output: str | None, root: Path | None, install: bool) -> int:
    out = Path(output) if output else Path.cwd() / f"{safe_name(shortcut.title)}.cia"
    cia.build(shortcut, out)
    print(f"Built {out}")
    print(f"  title    {shortcut.title}")
    if not shortcut.embed:
        print(f"  target   sdmc:{shortcut.target}")
    if shortcut.deliver:
        deliver = shortcut.deliver.rstrip(b"\0").decode(errors="replace")
        print(f"  deliver  {deliver}")
    if shortcut.embed:
        print(f"  native   {shortcut.embed.name} inside the CIA")
    print(f"  title id {shortcut.title_id():016X}")

    if install:
        if root is None:
            raise SystemExit("--install needs the SD card. Pass --sd.")
        dest = root / "cia" / out.name
        dest.parent.mkdir(exist_ok=True)
        if dest.resolve() != out.resolve():
            shutil.copyfile(out, dest)
        print(f"Copied to {dest}. Install it with FBI: SD > cia > {out.name}.")
    return 0


def locate(file: Path, a: argparse.Namespace) -> tuple[str, Path | None]:
    if a.target:
        return a.target, a.sd
    if a.native and (a.sd or sd_root_of(file)) is None:
        return "/" + file.name, None
    return sd_target(file, a.sd)


def cmd_make(a: argparse.Namespace) -> int:
    app = Path(a.app)
    if not app.is_file():
        raise SystemExit(f"{app} does not exist.")
    if a.native and (a.arg or a.deliver_arg):
        raise SystemExit("--native apps start from the HOME Menu, so they get no --arg or --deliver-arg.")
    target, root = locate(app, a)

    raw = threedsx.read_smdh(app)
    try:
        info = smdh.parse(raw) if raw else None
    except ValueError:
        info = None
    title = a.title or (info and info.short_title) or app.stem
    icon = load_icon(a.icon) or (info and info.icon) or Image.new("RGB", (48, 48), DEFAULT_ICON_COLOUR)
    shortcut = cia.Shortcut(
        target=target,
        title=title,
        publisher=a.publisher or (info and info.publisher) or "",
        icon=icon,
        args=tuple(a.arg),
        deliver=(a.deliver_arg.encode() + b"\0") if a.deliver_arg else b"",
        unique_id=parse_unique_id(a.unique_id),
        embed=app if a.native else None,
    )
    if a.logo == "black":
        shortcut.logo_file = tools.black_logo()
    return build_and_report(shortcut, a.output, root, a.install)


def resolve_emulator(a: argparse.Namespace, root: Path | None) -> Path:
    if a.emulator:
        local = Path(a.emulator)
        if local.is_file():
            return local
        if root and (root / a.emulator.lstrip("/")).is_file():
            return root / a.emulator.lstrip("/")
        raise SystemExit(f"Cannot find the emulator {a.emulator}.")
    found = gba.find_emulator(root) if root else None
    if found is None:
        raise SystemExit(
            "No mGBA .3dsx found under SD:/3ds. Install an mGBA development build, or pass --emulator."
        )
    return found


def cmd_gba(a: argparse.Namespace) -> int:
    rom = Path(a.rom)
    if not rom.is_file():
        raise SystemExit(f"{rom} does not exist.")
    if not gba.is_gba_rom(rom):
        raise SystemExit(f"{rom} is not a GBA ROM.")
    rom_target, root = locate(rom, a)
    title = a.title or gba.title_from_name(rom)
    shortcut = cia.Shortcut(
        target=rom_target,
        title=title,
        publisher=a.publisher or "Game Boy Advance",
        icon=load_icon(a.icon) or gba.default_icon(title),
        unique_id=parse_unique_id(a.unique_id),
        id_key=rom_target,
    )

    if a.native:
        shortcut.embed = resolve_emulator(a, root)
        # mGBA opens romfs:/<the name in romfs:/filename> when that file exists.
        shortcut.romfs_files = {rom.name: rom, "filename": rom.name.encode()}
    elif a.emulator and root is None:
        shortcut.target = a.emulator
        shortcut.deliver = rom_target.encode() + b"\0"
    else:
        if root is None:
            raise SystemExit("Pass --sd so the shortcut can find mGBA on the card.")
        found = resolve_emulator(a, root)
        shortcut.target = "/" + found.resolve().relative_to(root.resolve()).as_posix()
        shortcut.deliver = rom_target.encode() + b"\0"
    if a.logo == "black":
        shortcut.logo_file = tools.black_logo()
    return build_and_report(shortcut, a.output, root, a.install)


def cmd_setup(a: argparse.Namespace) -> int:
    folder = setup.run(force=a.force)
    print(f"Tools are in {folder}.")
    return 0


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--sd", type=Path, help="SD card root (found from the file path when possible)")
    p.add_argument("--title", help="name on the HOME Menu")
    p.add_argument("--publisher", help="second line on the HOME Menu")
    p.add_argument("--icon", help="PNG to use as the icon (scaled to 48x48)")
    p.add_argument("--unique-id", help="hex unique id in F8000-FEFFF (default: from the path)")
    p.add_argument("-o", "--output", help="where to write the .cia")
    p.add_argument("--install", action="store_true", help="also copy the .cia to SD:/cia")
    p.add_argument(
        "--logo",
        choices=["homebrew", "black"],
        default="homebrew",
        help="screen shown while the app loads: the homebrew logo, or plain black",
    )
    p.add_argument(
        "--native",
        action="store_true",
        help="put the app inside the CIA so it opens as its own title (rebuild after app updates)",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="shortcut3ds", description="Make HOME Menu shortcuts for 3DS homebrew.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    m = sub.add_parser("make", help="make a CIA that opens a .3dsx from the HOME Menu")
    m.add_argument("app", help="the .3dsx file, ideally on the mounted SD card")
    m.add_argument("--target", help="SD path of the .3dsx, e.g. /3ds/app/app.3dsx")
    m.add_argument("--arg", action="append", default=[], help="extra argument for the app; repeatable")
    m.add_argument("--deliver-arg", help="text passed to the app as the APT deliver arg")
    _common(m)
    m.set_defaults(func=cmd_make)

    g = sub.add_parser("gba", help="make a CIA that opens a GBA ROM in mGBA from the HOME Menu")
    g.add_argument("rom", help="the .gba file, ideally on the mounted SD card")
    g.add_argument("--target", help="SD path of the ROM, e.g. /roms/gba/game.gba")
    g.add_argument("--emulator", help="SD path of mGBA (default: the first mgba*.3dsx under SD:/3ds)")
    _common(g)
    g.set_defaults(func=cmd_gba)

    s = sub.add_parser("setup", help="download makerom and bannertool for this computer")
    s.add_argument("--force", action="store_true", help="download again even when present")
    s.set_defaults(func=cmd_setup)

    a = p.parse_args(argv)
    try:
        return a.func(a)
    except (tools.ToolError, setup.SetupError, threedsx.ThreeDsxError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
