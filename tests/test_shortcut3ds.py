import hashlib
import io
import os
import struct
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from shortcut3ds import cia, cli, gba, logo, native, setup, smdh, threedsx, tools

ICON = Image.new("RGB", (48, 48))


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


def make_3dsx(path: Path, smdh_raw: bytes | None) -> Path:
    header = bytearray(b"3DSX")
    if smdh_raw is None:
        header += struct.pack("<HHI", 0x20, 0, 0) + bytes(0x14)
        path.write_bytes(bytes(header))
    else:
        header += struct.pack("<HHI", 0x2C, 0, 0) + bytes(0x14)
        header += struct.pack("<III", 0x2C, len(smdh_raw), 0)
        path.write_bytes(bytes(header) + smdh_raw)
    return path


def test_icon_round_trips_through_the_tiled_layout():
    icon = Image.new("RGB", (48, 48))
    for x in range(48):
        for y in range(48):
            icon.putpixel((x, y), ((x * 5) & 0xF8, (y * 5) & 0xFC, ((x + y) * 2) & 0xF8))
    decoded = smdh.decode_icon(encode_icon(icon), 48)
    assert [p >> 3 for p in decoded.getpixel((13, 37))] == [p >> 3 for p in icon.getpixel((13, 37))]
    assert decoded.getpixel((47, 47))[0] >> 3 == icon.getpixel((47, 47))[0] >> 3


def test_reads_title_and_publisher_from_a_3dsx(tmp_path):
    raw = make_smdh("My App", "Me", Image.new("RGB", (48, 48), (255, 0, 0)))
    info = smdh.parse(threedsx.read_smdh(make_3dsx(tmp_path / "a.3dsx", raw)))
    assert (info.short_title, info.publisher) == ("My App", "Me")
    assert info.icon.getpixel((0, 0)) == (255, 0, 0)


def test_3dsx_without_extended_header_has_no_smdh(tmp_path):
    assert threedsx.read_smdh(make_3dsx(tmp_path / "a.3dsx", None)) is None


def test_rejects_a_file_that_is_not_3dsx(tmp_path):
    (tmp_path / "x.3dsx").write_bytes(b"NOPE" + bytes(64))
    with pytest.raises(threedsx.ThreeDsxError):
        threedsx.read_smdh(tmp_path / "x.3dsx")


def test_target_blob_puts_args_after_the_path():
    assert cia.target_blob("/3ds/a.3dsx", ("-x", "y")) == b"/3ds/a.3dsx\0-x\0y\0\0"


@pytest.mark.parametrize("bad", ["3ds/a.3dsx", "sdmc:/3ds/a.3dsx", "/a\0b"])
def test_target_blob_needs_an_absolute_sd_path(bad):
    with pytest.raises(ValueError):
        cia.target_blob(bad, ())


def test_unique_id_is_stable_and_in_the_homebrew_range():
    a = cia.Shortcut("/3ds/emerald3ds/Emerald3DS.3dsx", "t", "p", ICON)
    b = cia.Shortcut("/3DS/EMERALD3DS/Emerald3DS.3dsx", "t", "p", ICON)
    assert a.resolved_unique_id() == b.resolved_unique_id()
    assert cia.UNIQUE_ID_FIRST <= a.resolved_unique_id() < cia.UNIQUE_ID_FIRST + cia.UNIQUE_ID_COUNT
    assert a.title_id() >> 32 == 0x00040000


def test_sd_target_is_relative_to_the_card_root(tmp_path):
    (tmp_path / "Nintendo 3DS").mkdir()
    app = tmp_path / "3ds" / "app" / "app.3dsx"
    app.parent.mkdir(parents=True)
    app.touch()
    assert cli.sd_target(app, None) == ("/3ds/app/app.3dsx", tmp_path)


def test_rsf_has_no_bare_colon_list_items():
    text = cia.rsf(cia.Shortcut("/a.3dsx", "t", "p", ICON), Path("/r"))
    assert not [line for line in text.splitlines() if line.strip().startswith("- ") and line.endswith(":")]


def make_gba(path: Path, title: bytes = b"POKEMON EMER") -> Path:
    rom = bytearray(0x200)
    rom[gba.TITLE_OFFSET : gba.TITLE_OFFSET + len(title)] = title
    rom[gba.FIXED_VALUE_OFFSET] = 0x96
    path.write_bytes(bytes(rom))
    return path


def test_gba_title_drops_region_and_revision_tags(tmp_path):
    rom = make_gba(tmp_path / "Pokemon - Emerald Version (USA, Europe) [!].gba")
    assert gba.title_from_name(rom) == "Pokemon - Emerald Version"


def test_gba_title_falls_back_to_the_header(tmp_path):
    assert gba.title_from_name(make_gba(tmp_path / "(USA).gba")) == "Pokemon Emer"


def test_gba_rom_check_uses_the_fixed_header_byte(tmp_path):
    assert gba.is_gba_rom(make_gba(tmp_path / "a.gba"))
    (tmp_path / "b.gba").write_bytes(bytes(0x200))
    assert not gba.is_gba_rom(tmp_path / "b.gba")


def test_gba_initials_skip_filler_words():
    assert gba._initials("The Legend of Zelda") == "LZ"
    assert gba._initials("Pokemon - Emerald Version") == "PE"


def test_gba_shortcuts_for_two_roms_get_different_ids():
    a = cia.Shortcut("/3ds/mgba.3dsx", "a", "", ICON, id_key="/roms/gba/a.gba")
    b = cia.Shortcut("/3ds/mgba.3dsx", "b", "", ICON, id_key="/roms/gba/b.gba")
    assert a.resolved_unique_id() != b.resolved_unique_id()


def test_find_emulator_looks_under_3ds(tmp_path):
    (tmp_path / "3ds" / "mGBA").mkdir(parents=True)
    (tmp_path / "3ds" / "mGBA" / "mgba.3dsx").touch()
    (tmp_path / "3ds" / "mGBA" / "._mgba.3dsx").touch()
    assert gba.find_emulator(tmp_path) == tmp_path / "3ds" / "mGBA" / "mgba.3dsx"


def test_setup_rejects_a_download_with_the_wrong_hash(tmp_path, monkeypatch):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as z:
        z.writestr("makerom", b"binary")

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(setup.urllib.request, "urlopen", lambda *a, **k: Response(payload.getvalue()))
    with pytest.raises(setup.SetupError):
        setup.fetch(setup.Download("https://x/y.zip", "0" * 64, "makerom"), tmp_path / "makerom")
    assert not (tmp_path / "makerom").exists()

    good = hashlib.sha256(payload.getvalue()).hexdigest()
    setup.fetch(setup.Download("https://x/y.zip", good, "makerom"), tmp_path / "makerom")
    assert (tmp_path / "makerom").read_bytes() == b"binary"
    assert os.access(tmp_path / "makerom", os.X_OK)


def test_target_blob_rejects_args_the_stub_cannot_hold():
    with pytest.raises(ValueError):
        cia.target_blob("/3ds/a.3dsx", ("x" * cia.TARGET_BLOB_MAX,))


@pytest.mark.parametrize("arg", ["", "a\0b"])
def test_target_blob_rejects_empty_or_nul_args(arg):
    with pytest.raises(ValueError):
        cia.target_blob("/3ds/a.3dsx", (arg,))


def test_shortcuts_to_one_app_with_different_args_get_different_ids():
    plain = cia.Shortcut("/3ds/a.3dsx", "t", "", ICON)
    with_arg = cia.Shortcut("/3ds/a.3dsx", "t", "", ICON, args=("--fast",))
    with_deliver = cia.Shortcut("/3ds/a.3dsx", "t", "", ICON, deliver=b"/roms/x.gba\0")
    ids = {s.resolved_unique_id() for s in (plain, with_arg, with_deliver)}
    assert len(ids) == 3


@pytest.mark.parametrize("value", ["1000", "F7FFF", "FF000", "100000"])
def test_unique_id_outside_the_homebrew_range_is_rejected(value):
    with pytest.raises(ValueError):
        cli.parse_unique_id(value)


def test_unique_id_inside_the_range_is_accepted():
    assert cli.parse_unique_id("F9C19") == 0xF9C19


FIXTURES = Path(__file__).parent / "fixtures"


def _files(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_romfs_from_mkromfs3ds_unpacks_to_the_same_tree(tmp_path):
    count = native.extract_romfs((FIXTURES / "romfs.bin").read_bytes(), tmp_path)
    assert count == 5
    assert _files(tmp_path) == _files(FIXTURES / "romfs-src")
    assert (tmp_path / "empty").is_dir()


def _load_segments(elf: bytes) -> list[tuple[int, bytes, int, int]]:
    (phoff,) = struct.unpack_from("<I", elf, 0x1C)
    (phnum,) = struct.unpack_from("<H", elf, 0x2C)
    out = []
    for i in range(phnum):
        kind, off, vaddr, _, filesz, memsz, flags, _ = struct.unpack_from("<8I", elf, phoff + i * 32)
        if kind == 1:
            out.append((vaddr, elf[off : off + filesz], memsz, flags))
    return out


STUB = Path(__file__).parents[1] / "stub"


@pytest.mark.skipif(
    not (STUB / "stub.3dsx").exists(), reason="needs stub.elf and stub.3dsx from `make -C stub`"
)
def test_3dsx_converts_back_to_the_segments_of_its_elf():
    original = _load_segments((STUB / "stub.elf").read_bytes())
    converted = _load_segments(native.to_elf(native.load(STUB / "stub.3dsx")))
    assert converted == original


def test_3dsx_without_prm_is_refused(tmp_path):
    raw = (
        bytearray(b"3DSX") + struct.pack("<HHIIIIII", 0x20, 8, 0, 0, 0x10, 0, 0, 0) + bytes(24) + bytes(0x10)
    )
    (tmp_path / "x.3dsx").write_bytes(bytes(raw))
    with pytest.raises(threedsx.ThreeDsxError):
        native.load(tmp_path / "x.3dsx")


def test_black_logo_has_every_material_black_and_fits_its_slot():
    raw = tools.black_logo().read_bytes()
    assert len(raw) == 0x2000
    darc = logo.lz11_decompress(raw)
    colours = logo.material_colours(darc)
    assert len(colours) == 9
    assert all(black[:3] == b"\0\0\0" and white[:3] == b"\0\0\0" for _, black, white in colours)
    assert {"logo.bclim", "NintendoLogo_U_00.bclyt", "NintendoLogo_D_00.bclyt"} <= set(logo.darc_files(darc))


def test_lz11_round_trips():
    data = bytes(range(256)) * 40 + b"abc" * 3000 + bytes(5000)
    assert logo.lz11_decompress(logo.lz11_compress(data)) == data
