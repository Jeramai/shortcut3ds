from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PIL import Image

from shortcut3ds import cia

NATIVE, SHORTCUT = "native", "shortcut"
MODES = (NATIVE, SHORTCUT)

FILE, SD_PATH, TEXT = "file", "sd_path", "text"
LIST = "list"  # command line only


@dataclass(frozen=True)
class Option:
    name: str
    label: str
    needs: dict[str, str]
    help: str = ""
    sd_default: str = ""
    accept: str = ""
    link: str = ""
    bundled: str = ""

    def need(self, mode: str) -> str | None:
        return self.needs.get(mode)


@dataclass
class AppRef:
    file: Path | None = None
    sd_path: str | None = None


@dataclass
class Defaults:
    title: str
    publisher: str
    icon: Image.Image


@dataclass
class Request:
    file: Path
    target: str
    mode: str
    options: dict[str, object] = field(default_factory=dict)


@dataclass
class Look:
    title: str
    publisher: str
    icon: Image.Image
    unique_id: int | None = None


class Source(ABC):
    name: str
    label: str
    extensions: tuple[str, ...]
    sd_folder: str
    options: tuple[Option, ...] = ()
    notes: tuple[str, ...] = ()

    @abstractmethod
    def matches(self, path: Path) -> bool: ...

    @abstractmethod
    def defaults(self, path: Path) -> Defaults: ...

    @abstractmethod
    def shortcut(self, request: Request, look: Look) -> cia.Shortcut: ...

    def find(self, option: str, sd_root: Path) -> Path | None:
        return None

    def describe(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "extensions": list(self.extensions),
            "sd_folder": self.sd_folder,
            "notes": list(self.notes),
            "options": [asdict(o) for o in self.options],
        }
