import argparse
import shutil
import struct
import sys
from pathlib import Path

from shortcut3ds import __version__, cia, setup, sources, threedsx, tools
from shortcut3ds.common import load_icon, parse_unique_id, safe_name
from shortcut3ds.sources.base import (
    FILE,
    LIST,
    MODES,
    NATIVE,
    SD_PATH,
    SHORTCUT,
    AppRef,
    Look,
    Option,
    Request,
)


def sd_root_of(path: Path) -> Path | None:
    parts = path.resolve().parts
    if len(parts) >= 3 and parts[1] == "Volumes":
        return Path(*parts[:3])
    for parent in path.resolve().parents:
        if (parent / "Nintendo 3DS").is_dir():
            return parent
    return None


def sd_path_of(file: Path, root: Path | None) -> str | None:
    if root is None or not file.resolve().is_relative_to(root.resolve()):
        return None
    return "/" + file.resolve().relative_to(root.resolve()).as_posix()


def locate(file: Path, a: argparse.Namespace, mode: str) -> tuple[str, Path | None]:
    root = a.sd or sd_root_of(file)
    if a.target:
        return a.target, root
    on_card = sd_path_of(file, root)
    if on_card:
        return on_card, root
    if mode == NATIVE:
        return "/" + file.name, root
    if root is None:
        raise SystemExit("Cannot tell where the SD card starts. Pass --sd or --target.")
    raise SystemExit(f"{file} is not on the SD card at {root}. Pass --target with its path on the card.")


def app_ref(source: sources.Source, name: str, value: str | None, root: Path | None) -> AppRef:
    if value:
        local = Path(value)
        if not local.is_file() and root and (root / value.lstrip("/")).is_file():
            local = root / value.lstrip("/")
        if local.is_file():
            return AppRef(file=local, sd_path=sd_path_of(local, root))
        if value.startswith("/"):
            return AppRef(sd_path=value)
        raise SystemExit(f"Cannot find {value}.")
    found = source.find(name, root) if root else None
    return AppRef(file=found, sd_path=sd_path_of(found, root)) if found else AppRef()


def with_bundled(ref: AppRef, option: Option, need: str, a: argparse.Namespace, root: Path | None) -> AppRef:
    included = tools.bundled(option.bundled)
    if included is None:
        return ref
    if need == FILE and ref.file is None:
        return AppRef(file=included, sd_path=ref.sd_path)
    if need == SD_PATH and not ref.sd_path and a.install and root and option.sd_default:
        dest = root / option.sd_default.lstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(included, dest)
        print(f"Copied the included {option.bundled} to {dest}.")
        return AppRef(file=dest, sd_path=option.sd_default)
    return ref


def flag(name: str) -> str:
    return "--" + name.replace("_", "-")


def report(shortcut: cia.Shortcut, out: Path) -> None:
    print(f"Built {out}")
    print(f"  title    {shortcut.title}")
    if shortcut.embed:
        print(f"  native   {shortcut.embed.name} inside the CIA")
    else:
        print(f"  target   sdmc:{shortcut.target}")
    if shortcut.deliver:
        deliver = shortcut.deliver.rstrip(b"\0").decode(errors="replace")
        print(f"  deliver  {deliver}")
    print(f"  title id {shortcut.title_id():016X}")


def cmd_make(a: argparse.Namespace) -> int:
    file = Path(a.file)
    if not file.is_file():
        raise SystemExit(f"{file} does not exist.")
    source = sources.detect(file)
    mode = NATIVE if a.native else SHORTCUT
    target, root = locate(file, a, mode)

    own = {option.name for option in source.options}
    for other in sources.SOURCES:
        for option in other.options:
            if option.name not in own and getattr(a, option.name, None):
                raise SystemExit(f"{flag(option.name)} is not used with {source.label} files.")

    options: dict[str, object] = {}
    for option in source.options:
        value = getattr(a, option.name, None)
        need = option.need(mode)
        if need in (FILE, SD_PATH):
            options[option.name] = with_bundled(
                app_ref(source, option.name, value, root), option, need, a, root
            )
        elif value:
            if need is None:
                raise SystemExit(
                    f"{flag(option.name)} is not used with {'--native' if a.native else 'shortcuts'}."
                )
            options[option.name] = value

    defaults = source.defaults(file)
    look = Look(
        title=a.title or defaults.title,
        publisher=a.publisher if a.publisher is not None else defaults.publisher,
        icon=load_icon(a.icon) or defaults.icon,
        unique_id=parse_unique_id(a.unique_id),
    )
    try:
        shortcut = sources.build(source, Request(file, target, mode, options), look)
    except sources.MissingOption as e:
        hint = f"Pass {flag(e.option.name)}."
        if e.need == SD_PATH and tools.bundled(e.option.bundled):
            hint = f"Add --install to copy the included {e.option.bundled} to the card, or pass {flag(e.option.name)}."
        elif e.need == FILE and e.option.bundled:
            hint = f"Run `shortcut3ds setup` to get the included {e.option.bundled}, or pass {flag(e.option.name)}."
        raise SystemExit(f"{e} {hint}") from None

    out = Path(a.output) if a.output else Path.cwd() / f"{safe_name(look.title)}.cia"
    cia.build(shortcut, out)
    report(shortcut, out)

    if a.install:
        if root is None:
            raise SystemExit("--install needs the SD card. Pass --sd.")
        dest = root / "cia" / out.name
        dest.parent.mkdir(exist_ok=True)
        if dest.resolve() != out.resolve():
            shutil.copyfile(out, dest)
        print(f"Copied to {dest}. Install it with FBI: SD > cia > {out.name}.")
    return 0


def cmd_types(a: argparse.Namespace) -> int:
    for source in sources.SOURCES:
        extensions = ", ".join(source.extensions)
        print(f"{source.name:6} {extensions:14} {source.label}")
        for option in source.options:
            modes = ", ".join(f"{m}: {option.needs[m]}" for m in MODES if m in option.needs)
            print(f"{'':6} {flag(option.name):14} {option.label} ({modes})")
    return 0


def cmd_setup(a: argparse.Namespace) -> int:
    folder = setup.run(force=a.force)
    print(f"Tools are in {folder}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="shortcut3ds", description="Put 3DS homebrew and GBA games on the HOME Menu."
    )
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    m = sub.add_parser("make", help="make a CIA for a .3dsx app or a GBA ROM")
    m.add_argument("file", help="the file, ideally on the mounted SD card")
    m.add_argument(
        "--native", action="store_true", help="put the app inside the CIA (rebuild after app updates)"
    )
    m.add_argument("--sd", type=Path, help="SD card root (found from the file path when possible)")
    m.add_argument("--target", help="SD path of the file, e.g. /3ds/app/app.3dsx")
    m.add_argument("--title", help="name on the HOME Menu")
    m.add_argument("--publisher", help="second line on the HOME Menu")
    m.add_argument("--icon", help="PNG to use as the icon (scaled to 48x48)")
    m.add_argument("--unique-id", help="hex unique id in F8000-FEFFF (default: from the path)")
    m.add_argument("-o", "--output", help="where to write the .cia")
    m.add_argument("--install", action="store_true", help="also copy the .cia to SD:/cia")
    seen = set()
    for source in sources.SOURCES:
        for option in source.options:
            if option.name in seen:
                continue
            seen.add(option.name)
            repeat = LIST in option.needs.values()
            m.add_argument(
                flag(option.name),
                dest=option.name,
                action="append" if repeat else "store",
                help=f"{source.name}: your own {option.label} (default: the included one)"
                if option.bundled
                else f"{source.name}: {option.label}",
            )
    m.set_defaults(func=cmd_make)

    t = sub.add_parser("types", help="list the supported file types and their options")
    t.set_defaults(func=cmd_types)

    s = sub.add_parser("setup", help="download makerom and bannertool for this computer")
    s.add_argument("--force", action="store_true", help="download again even when present")
    s.set_defaults(func=cmd_setup)

    a = p.parse_args(argv)
    try:
        return a.func(a)
    except (
        tools.ToolError,
        setup.SetupError,
        threedsx.ThreeDsxError,
        ValueError,
        OSError,
        struct.error,
    ) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
