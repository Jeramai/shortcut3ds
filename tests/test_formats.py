import pytest
from helpers import encode_icon, make_3dsx, make_smdh
from PIL import Image

from shortcut3ds import smdh, threedsx


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
    assert threedsx.read_smdh(make_3dsx(tmp_path / "a.3dsx")) is None


def test_rejects_a_file_that_is_not_3dsx(tmp_path):
    (tmp_path / "x.3dsx").write_bytes(b"NOPE" + bytes(64))
    with pytest.raises(threedsx.ThreeDsxError):
        threedsx.read_smdh(tmp_path / "x.3dsx")
