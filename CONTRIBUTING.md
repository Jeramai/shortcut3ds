# Contributing

Thanks for helping. Bug reports, console test results and new file types are all welcome.

## Set up

You need Python 3.10+, and Docker for the 3DS stub and the website.

```sh
git clone https://github.com/Jeramai/shortcut3ds && cd shortcut3ds
make stub                    # stub.elf and stub.3dsx, built in the devkitpro/devkitarm image
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/shortcut3ds setup  # makerom and bannertool for this computer
make test
```

Before you open a pull request, run all four gates:

```sh
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/python -m pytest
scripts/build_web.sh         # only when you change the website or a file type
```

## Add a file type

A file type is one class in `src/shortcut3ds/sources/`. The command line and the website both read
the list of types from `SOURCES`, so a new type needs no CLI flags and no JavaScript.

`sources/gba.py` is the complete example: it detects a GBA ROM, gives it a title and an icon, needs
mGBA, and works in both modes. Copy it as a start.

### 1. Write the class

```python
from pathlib import Path

from shortcut3ds import cia
from shortcut3ds.sources.base import FILE, NATIVE, SD_PATH, SHORTCUT, Defaults, Look, Option, Request, Source


class Nes(Source):
    name = "nes"                        # used in URLs, JSON and tests; never change it later
    label = "NES ROM, opens in an emulator"
    extensions = (".nes",)
    sd_folder = "/roms/nes"             # where users usually keep these files
    options = (
        Option(
            "emulator",
            "Emulator .3dsx",
            {NATIVE: FILE, SHORTCUT: SD_PATH},
            help="Which emulator builds can open a ROM at startup.",
            sd_default="/3ds/emulator/emulator.3dsx",
            accept=".3dsx",
        ),
    )
    notes = ("Anything the user must know before they install it.",)

    def matches(self, path: Path) -> bool:
        with path.open("rb") as f:
            return f.read(4) == b"NES\x1a"   # check the content, not only the extension

    def defaults(self, path: Path) -> Defaults:
        return Defaults(title=path.stem, publisher="NES", icon=...)

    def shortcut(self, request: Request, look: Look) -> cia.Shortcut:
        ...
```

`Option.needs` says, per mode, what the option is:

| Need | Meaning | CLI | Website |
| :--- | :--- | :--- | :--- |
| `FILE` | A local file that goes inside the CIA | `--emulator PATH` | file picker |
| `SD_PATH` | Where a file is on the SD card | `--emulator /3ds/x.3dsx` | text field |
| `TEXT` | Optional free text | `--name TEXT` | text field |
| `LIST` | Repeatable text | `--name A --name B` | not shown |

Set `bundled="name.3dsx"` when the project ships a tested copy of the app (like mGBA). Then the
website and the CLI use that copy when the user chooses none, and `--install` copies it to
`sd_default` for shortcuts. Shipping a copy also needs a release asset, an entry in
`setup.COMMON`, a line in `scripts/build_web.sh` and an entry in `NOTICE.md` with its licence and
source.

Leave a mode out of `needs` when the option does not apply to it. `sources.build()` checks that the
required options are present before it calls `shortcut()`, so `shortcut()` can rely on them. A
`FILE` or `SD_PATH` option arrives as an `AppRef` with `.file` and `.sd_path`.

### 2. Fill in the shortcut

`shortcut()` returns a `cia.Shortcut`. Set these fields:

- `target`, `title`, `publisher`, `icon` and `unique_id`. Take the last four from `look`.
- **Native mode:** `embed`, the `.3dsx` to put inside the CIA. Add `romfs_files` for extra files in
  its RomFS.
- **Shortcut mode:** set `target` to the SD path of the `.3dsx` to start. Use `args` and/or
  `deliver` (the APT deliver arg) to tell it what to open.
- `id_key`, when the default unique ID must come from something other than `target`. For an
  emulator type, use the ROM path, so that two ROMs never share an ID.

**Never change how an existing type derives its unique ID.** Installed icons are keyed by it; a new
ID installs as a second icon. `tests/test_sources.py` pins the IDs of the built-in types.

### 3. Register it

Add an instance to `SOURCES` in `src/shortcut3ds/sources/__init__.py`. The order matters only when
two types could match the same file; the first match wins.

### 4. Test it

Add a small synthetic sample to `SAMPLES` in `tests/test_sources.py`, built in code from
`tests/helpers.py`. The shared tests then check your type: that it describes itself, matches its
own sample and no other, builds a shortcut in every mode, and reports missing options.

Add tests for any parsing that your type does, like the GBA title and initials tests.

**Never commit a real ROM, app, save file or CIA**, not even a small one. `.gitignore` blocks the
usual extensions; build test data in code.

### 5. Test it on a console

In the pull request, say which console and Luma3DS version you used, which mode, and what happened
when you opened and closed the icon. A pull request for a new type needs at least one console test.

## Other changes

- **The stub** (`stub/source/main.c`) runs on the console before the app. Keep it small, and test any
  change on hardware.
- **The website** (`web/`) has no build step of its own. `scripts/build_web.sh` copies it into
  `site/`; serve that folder with `python3 -m http.server -d site` to try it.
- **Comments:** at most one short line, and only for what the code cannot say: a trap, an outside
  constraint, or why something is absent. Put the reasoning in the commit message.
- **Commits** use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `refactor:`.

## Licence

By contributing, you agree that your contribution is licensed under the MIT licence of this project.
