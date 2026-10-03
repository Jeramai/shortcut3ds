import struct
from dataclasses import dataclass
from pathlib import Path

from shortcut3ds.threedsx import BASIC_HEADER_SIZE, ThreeDsxError

BASE_ADDRESS = 0x00100000
PAGE = 0x1000
PRM_MAGIC = b"_prm"

PF_X, PF_W, PF_R = 1, 2, 4
EMPTY = 0xFFFFFFFF


def _page_align(n: int) -> int:
    return (n + PAGE - 1) & ~(PAGE - 1)


@dataclass
class Segment:
    address: int
    data: bytes
    mem_size: int
    flags: int


@dataclass
class Program:
    text: Segment
    rodata: Segment
    data: Segment
    romfs: bytes | None


def load(path: Path) -> Program:
    raw = path.read_bytes()
    if raw[:4] != b"3DSX":
        raise ThreeDsxError(f"{path} is not a 3DSX file")
    header_size, reloc_hdr_size = struct.unpack_from("<HH", raw, 4)
    code_size, rodata_size, data_size, bss_size = struct.unpack_from("<IIII", raw, 0x10)
    romfs_offset = 0
    if header_size > BASIC_HEADER_SIZE:
        romfs_offset = struct.unpack_from("<I", raw, BASIC_HEADER_SIZE + 8)[0]

    sizes = [_page_align(code_size), _page_align(rodata_size), _page_align(data_size)]
    addrs = [BASE_ADDRESS, BASE_ADDRESS + sizes[0], BASE_ADDRESS + sizes[0] + sizes[1]]
    bounds = [sizes[0], sizes[0] + sizes[1]]

    n_tables = reloc_hdr_size // 4
    pos = header_size
    reloc_counts = []
    for _ in range(3):
        reloc_counts.append(struct.unpack_from(f"<{n_tables}I", raw, pos))
        pos += reloc_hdr_size

    image = bytearray(sum(sizes))
    loaded = [code_size, rodata_size, data_size - bss_size]
    starts = [0, sizes[0], sizes[0] + sizes[1]]
    for seg in range(3):
        image[starts[seg] : starts[seg] + loaded[seg]] = raw[pos : pos + loaded[seg]]
        pos += loaded[seg]

    def translate(offset: int) -> int:
        if offset < bounds[0]:
            return addrs[0] + offset
        if offset < bounds[1]:
            return addrs[1] + offset - bounds[0]
        return addrs[2] + offset - bounds[1]

    for seg in range(3):
        end = (starts[seg] + sizes[seg]) // 4
        for table, count in enumerate(reloc_counts[seg]):
            entries = struct.unpack_from(f"<{count * 2}H", raw, pos)
            pos += count * 4
            if table > 1:
                continue
            word = starts[seg] // 4
            for skip, patch in zip(entries[::2], entries[1::2]):
                word += skip
                for _ in range(patch):
                    if word >= end:
                        break
                    (orig,) = struct.unpack_from("<I", image, word * 4)
                    sub_type = orig >> 28
                    target = translate(orig & 0x0FFFFFFF)
                    if table == 0:
                        if sub_type != 0:
                            raise ThreeDsxError(f"unsupported absolute relocation subtype {sub_type}")
                        value = target
                    else:
                        value = (target - (BASE_ADDRESS + word * 4)) & 0xFFFFFFFF
                        if sub_type == 1:
                            value &= 0x7FFFFFFF
                        elif sub_type != 0:
                            raise ThreeDsxError(f"unsupported relative relocation subtype {sub_type}")
                    struct.pack_into("<I", image, word * 4, value)
                    word += 1

    if image[4:8] != PRM_MAGIC:
        raise ThreeDsxError(f"{path} was not built with libctru; it cannot run as a CIA")

    romfs = raw[romfs_offset:] if romfs_offset else None
    return Program(
        text=Segment(addrs[0], bytes(image[: loaded[0]]), loaded[0], PF_R | PF_X),
        rodata=Segment(addrs[1], bytes(image[starts[1] : starts[1] + loaded[1]]), loaded[1], PF_R),
        data=Segment(addrs[2], bytes(image[starts[2] : starts[2] + loaded[2]]), data_size, PF_R | PF_W),
        romfs=romfs or None,
    )


def to_elf(program: Program) -> bytes:
    segments = [s for s in (program.text, program.rodata, program.data) if s.data or s.mem_size]
    ehdr_size, phdr_size, shdr_size = 52, 32, 40
    shstrtab = b"\0.shstrtab\0"
    data_offset = _page_align(ehdr_size + phdr_size * len(segments))

    body = bytearray()
    phdrs = bytearray()
    for seg in segments:
        offset = data_offset + len(body)
        body += seg.data
        body += bytes(_page_align(len(body)) - len(body))
        phdrs += struct.pack(
            "<8I", 1, offset, seg.address, seg.address, len(seg.data), seg.mem_size, seg.flags, PAGE
        )

    strtab_offset = data_offset + len(body)
    shdr_offset = strtab_offset + len(shstrtab)
    shdrs = bytes(shdr_size) + struct.pack("<10I", 1, 3, 0, 0, strtab_offset, len(shstrtab), 0, 0, 1, 0)

    ehdr = b"\x7fELF" + bytes([1, 1, 1, 0]) + bytes(8)
    ehdr += struct.pack(
        "<HHIIIIIHHHHHH",
        2,  # ET_EXEC
        40,  # EM_ARM
        1,
        program.text.address,
        ehdr_size,
        shdr_offset,
        0x05000000,  # EABI version 5
        ehdr_size,
        phdr_size,
        len(segments),
        shdr_size,
        2,
        1,
    )
    head = ehdr + phdrs
    return head + bytes(data_offset - len(head)) + body + shstrtab + shdrs


def _name(raw: bytes, offset: int) -> str:
    (length,) = struct.unpack_from("<I", raw, offset)
    name = raw[offset + 4 : offset + 4 + length].decode("utf-16-le")
    if name in ("", ".", "..") or any(c in name for c in "/\\\0"):
        raise ThreeDsxError(f"the app's RomFS has an unsafe name {name!r}")
    return name


def extract_romfs(raw: bytes, dest: Path) -> int:
    (header_size, _, _, dir_table, _, _, _, file_table, _, file_data) = struct.unpack_from("<10I", raw, 0)
    if header_size != 0x28:
        raise ThreeDsxError("the app's RomFS has an unknown layout")
    count = 0
    seen: set[tuple[str, int]] = set()

    def visit(kind: str, offset: int) -> None:
        if (kind, offset) in seen:
            raise ThreeDsxError("the app's RomFS links back to itself")
        seen.add((kind, offset))

    def walk_dir(offset: int, path: Path) -> None:
        nonlocal count
        visit("dir", offset)
        path.mkdir(parents=True, exist_ok=True)
        _, _, child_dir, child_file, _ = struct.unpack_from("<5I", raw, dir_table + offset)
        while child_file != EMPTY:
            visit("file", child_file)
            entry = file_table + child_file
            _, sibling, data_off, data_size, _ = struct.unpack_from("<IIQQI", raw, entry)
            name = _name(raw, entry + 0x1C)
            start = file_data + data_off
            (path / name).write_bytes(raw[start : start + data_size])
            count += 1
            child_file = sibling
        while child_dir != EMPTY:
            entry = dir_table + child_dir
            _, sibling = struct.unpack_from("<2I", raw, entry)
            name = _name(raw, entry + 0x14)
            walk_dir(child_dir, path / name)
            child_dir = sibling

    walk_dir(0, dest)
    return count
