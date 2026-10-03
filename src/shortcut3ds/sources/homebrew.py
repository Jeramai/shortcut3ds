from pathlib import Path

from shortcut3ds import cia, smdh, threedsx
from shortcut3ds.common import placeholder_icon
from shortcut3ds.sources.base import LIST, NATIVE, SHORTCUT, TEXT, Defaults, Look, Option, Request, Source


def app_info(path: Path) -> smdh.Smdh | None:
    raw = threedsx.read_smdh(path)
    try:
        return smdh.parse(raw) if raw else None
    except ValueError:
        return None


class Homebrew(Source):
    name = "3dsx"
    label = "3DS homebrew app"
    extensions = (".3dsx",)
    sd_folder = "/3ds/{stem}"
    options = (
        Option("arg", "Extra argument for the app", {SHORTCUT: LIST}),
        Option("deliver_arg", "Text passed to the app as the APT deliver arg", {SHORTCUT: TEXT}),
    )

    def matches(self, path: Path) -> bool:
        with path.open("rb") as f:
            return f.read(4) == b"3DSX"

    def defaults(self, path: Path) -> Defaults:
        info = app_info(path)
        return Defaults(
            title=(info and info.short_title) or path.stem,
            publisher=(info and info.publisher) or "",
            icon=(info and info.icon) or placeholder_icon(),
        )

    def shortcut(self, request: Request, look: Look) -> cia.Shortcut:
        deliver = request.options.get("deliver_arg") or ""
        return cia.Shortcut(
            target=request.target,
            title=look.title,
            publisher=look.publisher,
            icon=look.icon,
            unique_id=look.unique_id,
            args=tuple(request.options.get("arg") or ()),
            deliver=deliver.encode() + b"\0" if deliver else b"",
            embed=request.file if request.mode == NATIVE else None,
        )
