import os
import struct
from pathlib import Path

import pytest
from helpers import FIXTURES, STUB, load_segments

from shortcut3ds import native, threedsx


def _files(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_romfs_from_mkromfs3ds_unpacks_to_the_same_tree(tmp_path):
    count = native.extract_romfs((FIXTURES / "romfs.bin").read_bytes(), tmp_path)
    assert count == 5
    assert _files(tmp_path) == _files(FIXTURES / "romfs-src")
    assert (tmp_path / "empty").is_dir()


def _romfs_with_one_file(name: str) -> bytes:
    encoded = name.encode("utf-16-le")
    dir_table = 0x28
    file_table = dir_table + 0x18
    file_data = file_table + 0x20 + len(encoded)
    header = struct.pack("<10I", 0x28, 0, 0, dir_table, 0x18, 0, 0, file_table, 0, file_data)
    root = struct.pack("<6I", 0, native.EMPTY, native.EMPTY, 0, native.EMPTY, 0)
    entry = struct.pack("<IIQQII", 0, native.EMPTY, 0, 1, native.EMPTY, len(encoded)) + encoded
    return header + root + entry + b"x"


@pytest.mark.parametrize("name", ["..", "../escape.txt", "/abs.txt"])
def test_romfs_names_cannot_leave_the_destination(tmp_path, name):
    dest = tmp_path / "romfs"
    with pytest.raises(threedsx.ThreeDsxError):
        native.extract_romfs(_romfs_with_one_file(name), dest)
    assert not (tmp_path / "escape.txt").exists()


def test_romfs_with_a_plain_name_extracts(tmp_path):
    assert native.extract_romfs(_romfs_with_one_file("ok.txt"), tmp_path) == 1
    assert (tmp_path / "ok.txt").read_bytes() == b"x"


@pytest.mark.skipif(
    not (STUB / "stub.3dsx").exists() and not os.environ.get("CI"),
    reason="needs stub.elf and stub.3dsx from `make stub`",
)
def test_3dsx_converts_back_to_the_segments_of_its_elf():
    original = load_segments((STUB / "stub.elf").read_bytes())
    converted = load_segments(native.to_elf(native.load(STUB / "stub.3dsx")))
    assert converted == original


def test_3dsx_without_prm_is_refused(tmp_path):
    raw = (
        bytearray(b"3DSX") + struct.pack("<HHIIIIII", 0x20, 8, 0, 0, 0x10, 0, 0, 0) + bytes(24) + bytes(0x10)
    )
    (tmp_path / "x.3dsx").write_bytes(bytes(raw))
    with pytest.raises(threedsx.ThreeDsxError):
        native.load(tmp_path / "x.3dsx")


def test_romfs_that_links_back_to_itself_is_refused(tmp_path):
    raw = bytearray(_romfs_with_one_file("loop.txt"))
    struct.pack_into("<I", raw, 0x28 + 0x18 + 4, 0)
    with pytest.raises(threedsx.ThreeDsxError):
        native.extract_romfs(bytes(raw), tmp_path)
