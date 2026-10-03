import struct
from pathlib import Path

import pytest
from PIL import Image

from shortcut3ds import cia, cli, smdh, threedsx
from shortcut3ds.cli import DEFAULT_ICON


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
    a = cia.Shortcut("/3ds/emerald3ds/Emerald3DS.3dsx", "t", "p", DEFAULT_ICON)
    b = cia.Shortcut("/3DS/EMERALD3DS/Emerald3DS.3dsx", "t", "p", DEFAULT_ICON)
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
    text = cia.rsf(cia.Shortcut("/a.3dsx", "t", "p", DEFAULT_ICON), Path("/r"))
    assert not [line for line in text.splitlines() if line.strip().startswith("- ") and line.endswith(":")]
