import argparse
import json

import pytest
from helpers import ICON, make_3dsx, make_gba, make_smdh
from PIL import Image

from shortcut3ds import cli, sources, web
from shortcut3ds.sources import gba
from shortcut3ds.sources.base import FILE, LIST, MODES, NATIVE, SD_PATH, SHORTCUT, TEXT, AppRef, Look, Request

SAMPLES = {
    "3dsx": lambda d: make_3dsx(d / "app.3dsx", make_smdh("My App", "Me", Image.new("RGB", (48, 48), "red"))),
    "gba": lambda d: make_gba(d / "Game (USA).gba"),
}


def filled_options(source, mode, tmp_path):
    options = {}
    for option in source.options:
        need = option.need(mode)
        if need in (FILE, SD_PATH):
            emulator = make_3dsx(tmp_path / f"{option.name}.3dsx")
            options[option.name] = AppRef(file=emulator, sd_path=f"/3ds/{option.name}.3dsx")
    return options


def test_every_source_has_a_sample_file():
    assert set(SAMPLES) == {s.name for s in sources.SOURCES}


@pytest.mark.parametrize("source", sources.SOURCES, ids=lambda s: s.name)
def test_source_describes_itself_completely(source):
    assert source.name and source.label and source.extensions and source.sd_folder.startswith("/")
    assert all(e.startswith(".") and e == e.lower() for e in source.extensions)
    for option in source.options:
        assert option.name.isidentifier()
        assert set(option.needs) <= set(MODES)
        assert set(option.needs.values()) <= {FILE, SD_PATH, TEXT, LIST}
    json.dumps(source.describe())


@pytest.mark.parametrize("source", sources.SOURCES, ids=lambda s: s.name)
def test_source_detects_its_own_sample_and_no_other(source, tmp_path):
    for name, make in SAMPLES.items():
        path = make(tmp_path)
        assert source.matches(path) == (name == source.name)


@pytest.mark.parametrize("source", sources.SOURCES, ids=lambda s: s.name)
@pytest.mark.parametrize("mode", MODES)
def test_source_builds_a_valid_shortcut_in_every_mode(source, mode, tmp_path):
    path = SAMPLES[source.name](tmp_path)
    defaults = source.defaults(path)
    assert defaults.title and defaults.icon.size[0] == defaults.icon.size[1]
    request = Request(path, "/some/where/" + path.name, mode, filled_options(source, mode, tmp_path))
    shortcut = sources.build(source, request, Look(defaults.title, defaults.publisher, defaults.icon))
    assert (shortcut.embed is not None) == (mode == NATIVE)
    assert shortcut.target.startswith("/")


WITH_REQUIRED = [s for s in sources.SOURCES if any(o.need(NATIVE) in (FILE, SD_PATH) for o in s.options)]


@pytest.mark.parametrize("source", WITH_REQUIRED, ids=lambda s: s.name)
def test_missing_required_option_is_reported(source, tmp_path):
    path = SAMPLES[source.name](tmp_path)
    with pytest.raises(sources.MissingOption):
        sources.build(source, Request(path, "/x/" + path.name, NATIVE, {}), Look("t", "", ICON))


def test_detect_names_the_supported_types_when_nothing_matches(tmp_path):
    (tmp_path / "x.bin").write_bytes(bytes(0x200))
    with pytest.raises(ValueError, match=r"\.3dsx.*\.gba"):
        sources.detect(tmp_path / "x.bin")


# Installed icons are keyed by these IDs; a new ID would install as a duplicate icon.
@pytest.mark.parametrize(
    ("name", "target", "mode", "expected"),
    [
        ("3dsx", "/3ds/emerald3ds/Emerald3DS.3dsx", SHORTCUT, "000400000FD1C700"),
        ("3dsx", "/3ds/emerald3ds/Emerald3DS.3dsx", NATIVE, "000400000F8FDB00"),
        ("gba", "/roms/gba/Pokemon Emerald.gba", SHORTCUT, "000400000F932E00"),
        ("gba", "/roms/gba/Pokemon Emerald.gba", NATIVE, "000400000F8ACC00"),
    ],
)
def test_title_ids_stay_stable(name, target, mode, expected, tmp_path):
    source = sources.get(name)
    path = SAMPLES[name](tmp_path)
    options = filled_options(source, mode, tmp_path)
    if name == "gba":
        options["emulator"] = AppRef(file=options["emulator"].file, sd_path="/3ds/mgba/mgba.3dsx")
    shortcut = sources.build(source, Request(path, target, mode, options), Look("t", "", ICON))
    assert f"{shortcut.title_id():016X}" == expected


def test_gba_title_drops_region_and_revision_tags(tmp_path):
    rom = make_gba(tmp_path / "Pokemon - Emerald Version (USA, Europe) [!].gba")
    assert gba.title_from_name(rom) == "Pokemon - Emerald Version"


def test_gba_title_falls_back_to_the_header(tmp_path):
    assert gba.title_from_name(make_gba(tmp_path / "(USA).gba")) == "Pokemon Emer"


def test_gba_initials_skip_filler_words():
    assert gba._initials("The Legend of Zelda") == "LZ"
    assert gba._initials("Pokemon - Emerald Version") == "PE"


def test_gba_finds_mgba_and_skips_appledouble_files(tmp_path):
    (tmp_path / "3ds" / "mGBA").mkdir(parents=True)
    (tmp_path / "3ds" / "mGBA" / "mgba.3dsx").touch()
    (tmp_path / "3ds" / "mGBA" / "._mgba.3dsx").touch()
    assert gba.Gba().find("emulator", tmp_path) == tmp_path / "3ds" / "mGBA" / "mgba.3dsx"


def test_cli_finds_the_sd_path_from_the_card_root(tmp_path):
    (tmp_path / "Nintendo 3DS").mkdir()
    app = tmp_path / "3ds" / "app" / "app.3dsx"
    app.parent.mkdir(parents=True)
    app.touch()
    args = argparse.Namespace(target=None, sd=None)
    assert cli.locate(app, args, SHORTCUT) == ("/3ds/app/app.3dsx", tmp_path)


def test_cli_native_app_off_the_card_keeps_the_sd_root(tmp_path):
    sd = tmp_path / "sd"
    sd.mkdir()
    app = tmp_path / "downloads" / "app.3dsx"
    app.parent.mkdir()
    app.touch()
    assert cli.locate(app, argparse.Namespace(target=None, sd=sd), NATIVE) == ("/app.3dsx", sd)


def test_cli_lists_every_type(capsys):
    assert cli.main(["types"]) == 0
    out = capsys.readouterr().out
    assert all(s.name in out for s in sources.SOURCES) and "--emulator" in out


def test_web_and_cli_agree_on_the_title_id(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "BASE", tmp_path)
    rom = make_gba(tmp_path / "Game (USA).gba")
    info = json.loads(web.inspect(str(rom)))
    assert info == {"source": "gba", "title": "Game", "publisher": "Game Boy Advance"}
    spec = {
        "source": "gba", "mode": SHORTCUT, "file": str(rom), "title": "Game", "publisher": "",
        "target": "/roms/gba/Game (USA).gba", "options": {"emulator": {"sd_path": "/3ds/mgba/mgba.3dsx"}},
    }  # fmt: skip
    plan = json.loads(web.prepare(json.dumps(spec)))
    request = Request(rom, spec["target"], SHORTCUT, {"emulator": AppRef(sd_path="/3ds/mgba/mgba.3dsx")})
    expected = sources.build(sources.get("gba"), request, Look("Game", "", ICON))
    assert plan["title_id"] == f"{expected.title_id():016X}"
    assert [c[0] for c in plan["commands"]] == ["bannertool", "bannertool", "makerom"]
    assert (tmp_path / "work" / "romfs" / "deliver").read_bytes() == b"/roms/gba/Game (USA).gba\0"


def test_web_describe_lists_every_type():
    assert [d["name"] for d in json.loads(web.describe())] == [s.name for s in sources.SOURCES]
