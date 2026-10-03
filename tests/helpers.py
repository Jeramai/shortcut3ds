import struct
from pathlib import Path

from PIL import Image

from shortcut3ds import smdh
from shortcut3ds.sources import gba

ICON = Image.new("RGB", (48, 48))
FIXTURES = Path(__file__).parent / "fixtures"
STUB = Path(__file__).parents[1] / "stub"


def encode_icon(img: Image.Image) -> bytes:
    out = bytearray()
    px = img.load()
    for ty in range(0, 48, 8):
        for tx in range(0, 48, 8):
            for k in range(64):
                x, y = smdh._morton(k)
                r, g, b = px[tx + x, ty + y]
                out += struct.pack("<H", (r >> 3) << 11 | (g >> 2) << 5 | b >> 3)
    return bytes(out)


def make_smdh(title: str, publisher: str, icon: Image.Image) -> bytes:
    raw = bytearray(smdh.SMDH_SIZE)
    raw[:4] = b"SMDH"
    entry = smdh.TITLES_OFFSET + smdh.ENGLISH * smdh.TITLE_SIZE
    raw[entry : entry + len(title) * 2] = title.encode("utf-16-le")
    raw[entry + 0x180 : entry + 0x180 + len(publisher) * 2] = publisher.encode("utf-16-le")
    raw[smdh.LARGE_ICON_OFFSET : smdh.LARGE_ICON_OFFSET + 48 * 48 * 2] = encode_icon(icon)
    return bytes(raw)


def make_3dsx(path: Path, smdh_raw: bytes | None = None) -> Path:
    header = bytearray(b"3DSX")
    if smdh_raw is None:
        header += struct.pack("<HHI", 0x20, 0, 0) + bytes(0x14)
        path.write_bytes(bytes(header))
    else:
        header += struct.pack("<HHI", 0x2C, 0, 0) + bytes(0x14)
        header += struct.pack("<III", 0x2C, len(smdh_raw), 0)
        path.write_bytes(bytes(header) + smdh_raw)
    return path


def make_gba(path: Path, title: bytes = b"POKEMON EMER") -> Path:
    rom = bytearray(0x200)
    rom[gba.TITLE_OFFSET : gba.TITLE_OFFSET + len(title)] = title
    rom[gba.FIXED_VALUE_OFFSET] = 0x96
    path.write_bytes(bytes(rom))
    return path


def load_segments(elf: bytes) -> list[tuple[int, bytes, int, int]]:
    (phoff,) = struct.unpack_from("<I", elf, 0x1C)
    (phnum,) = struct.unpack_from("<H", elf, 0x2C)
    out = []
    for i in range(phnum):
        kind, off, vaddr, _, filesz, memsz, flags, _ = struct.unpack_from("<8I", elf, phoff + i * 32)
        if kind == 1:
            out.append((vaddr, elf[off : off + filesz], memsz, flags))
    return out
