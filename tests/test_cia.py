from pathlib import Path

import pytest
from helpers import ICON

from shortcut3ds import cia


def test_target_blob_puts_args_after_the_path():
    assert cia.target_blob("/3ds/a.3dsx", ("-x", "y")) == b"/3ds/a.3dsx\0-x\0y\0\0"


@pytest.mark.parametrize("bad", ["3ds/a.3dsx", "sdmc:/3ds/a.3dsx", "/a\0b"])
def test_target_blob_needs_an_absolute_sd_path(bad):
    with pytest.raises(ValueError):
        cia.target_blob(bad, ())


def test_target_blob_rejects_args_the_stub_cannot_hold():
    with pytest.raises(ValueError):
        cia.target_blob("/3ds/a.3dsx", ("x" * cia.TARGET_BLOB_MAX,))


@pytest.mark.parametrize("arg", ["", "a\0b"])
def test_target_blob_rejects_empty_or_nul_args(arg):
    with pytest.raises(ValueError):
        cia.target_blob("/3ds/a.3dsx", (arg,))


def test_unique_id_is_stable_and_in_the_homebrew_range():
    a = cia.Shortcut("/3ds/emerald3ds/Emerald3DS.3dsx", "t", "p", ICON)
    b = cia.Shortcut("/3DS/EMERALD3DS/Emerald3DS.3dsx", "t", "p", ICON)
    assert a.resolved_unique_id() == b.resolved_unique_id()
    assert cia.UNIQUE_ID_FIRST <= a.resolved_unique_id() < cia.UNIQUE_ID_FIRST + cia.UNIQUE_ID_COUNT
    assert a.title_id() >> 32 == 0x00040000


def test_shortcuts_to_one_app_with_different_args_get_different_ids():
    plain = cia.Shortcut("/3ds/a.3dsx", "t", "", ICON)
    with_arg = cia.Shortcut("/3ds/a.3dsx", "t", "", ICON, args=("--fast",))
    with_deliver = cia.Shortcut("/3ds/a.3dsx", "t", "", ICON, deliver=b"/roms/x.gba\0")
    ids = {s.resolved_unique_id() for s in (plain, with_arg, with_deliver)}
    assert len(ids) == 3


def test_gba_shortcuts_for_two_roms_get_different_ids():
    a = cia.Shortcut("/3ds/mgba.3dsx", "a", "", ICON, id_key="/roms/gba/a.gba")
    b = cia.Shortcut("/3ds/mgba.3dsx", "b", "", ICON, id_key="/roms/gba/b.gba")
    assert a.resolved_unique_id() != b.resolved_unique_id()


def test_rsf_has_no_bare_colon_list_items():
    text = cia.rsf(cia.Shortcut("/a.3dsx", "t", "p", ICON), Path("/r"))
    assert not [line for line in text.splitlines() if line.strip().startswith("- ") and line.endswith(":")]
