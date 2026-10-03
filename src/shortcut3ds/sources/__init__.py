from pathlib import Path

from shortcut3ds import cia
from shortcut3ds.sources.base import FILE, LIST, SD_PATH, AppRef, Look, Option, Request, Source
from shortcut3ds.sources.gba import Gba
from shortcut3ds.sources.homebrew import Homebrew

SOURCES: tuple[Source, ...] = (Homebrew(), Gba())


class MissingOption(ValueError):
    def __init__(self, source: Source, option: Option, need: str):
        self.option, self.need = option, need
        what = "the file" if need == FILE else "its path on the SD card"
        super().__init__(f"{source.label}: {option.label} is needed ({what}). {option.help}".strip())


def detect(path: Path) -> Source:
    for source in SOURCES:
        if source.matches(path):
            return source
    kinds = ", ".join(e for s in SOURCES for e in s.extensions)
    raise ValueError(f"{path.name} is not a supported file ({kinds}).")


def get(name: str) -> Source:
    for source in SOURCES:
        if source.name == name:
            return source
    raise ValueError(f"unknown file type {name}")


def describe() -> list[dict]:
    return [source.describe() for source in SOURCES]


def build(source: Source, request: Request, look: Look) -> cia.Shortcut:
    for option in source.options:
        need = option.need(request.mode)
        value = request.options.get(option.name)
        if need is None:
            if value:
                raise ValueError(f"{option.label} is not used in {request.mode} mode.")
        elif need in (FILE, SD_PATH):
            ref = value if isinstance(value, AppRef) else AppRef()
            if (need == FILE and ref.file is None) or (need == SD_PATH and not ref.sd_path):
                raise MissingOption(source, option, need)
            request.options[option.name] = ref
        elif need == LIST and value is not None and not isinstance(value, list | tuple):
            raise ValueError(f"{option.label} must be a list.")
    return source.shortcut(request, look)
