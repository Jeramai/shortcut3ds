import struct
from pathlib import Path

import pytest
from PIL import Image

from shortcut3ds import cia, cli, gba, smdh, threedsx

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
    assert gba.find_emulator(tmp_path) == tmp_path / "3ds" / "mGBA" / "mgba.3dsx"
