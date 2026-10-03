# shortcut3ds

Put 3DS homebrew apps (`.3dsx`) and GBA games on the HOME Menu as real icons.

**Use it in your browser: [jeramai.github.io/shortcut3ds](https://jeramai.github.io/shortcut3ds/)**.
Nothing is uploaded; the converter runs in the tab. There is also a command line tool for macOS
and Linux.

> **Status: alpha.** Tested on one console with Luma3DS. Please report what happens on yours.

## Two kinds of icon

| | Native | Shortcut |
| :--- | :--- | :--- |
| How it opens | As its own title, like an installed game | Through the Homebrew Launcher Loader title |
| What the CIA holds | A copy of the app (and, for GBA, mGBA and the ROM) | Only a path to the app on the SD card |
| After an app update | Build the CIA again | Nothing to do |
| Size | The size of the app | About 180 KB |

Both keep the app's own icon and name, and both show the standard homebrew logo for a moment while
the app loads. The HOME Menu does not open a title without that logo.

## Requirements

On the console:

- Custom firmware with **Luma3DS**, and **FBI** to install the `.cia`.
- **Shortcut mode only:** the Homebrew Launcher Loader title `000400000D921E00`. Install
  [`hblauncher_loader.cia`](https://github.com/yellows8/hblauncher_loader/releases) once with FBI.
  Luma replaces its code with the requested app, so its age does not matter.
- **GBA games:** an mGBA [development build](https://mgba.io/downloads.html#development-downloads)
  for 3DS. mGBA 0.10.x releases cannot open a ROM at startup.

## Command line

Python 3.10 or newer on macOS or Linux. Download the `.whl` from the
[latest release](https://github.com/Jeramai/shortcut3ds/releases/latest), then:

```sh
pipx install ./shortcut3ds-*-py3-none-any.whl
shortcut3ds setup
```

`setup` downloads [makerom](https://github.com/3DSGuy/Project_CTR) and
[bannertool](https://github.com/carstene1ns/3ds-bannertool) to `~/.local/share/shortcut3ds/bin` and
checks their SHA-256. A copy on `PATH` wins, and so do `SHORTCUT3DS_MAKEROM` and
`SHORTCUT3DS_BANNERTOOL`.

Mount the SD card and point at the file on it:

```sh
shortcut3ds make /Volumes/3DS/3ds/myapp/myapp.3dsx --native --install
shortcut3ds gba "/Volumes/3DS/roms/gba/Pokemon Emerald.gba" --native --install
```

`--install` copies the `.cia` to `SD:/cia/`. On the console, open FBI, go to **SD > cia**, and
install it. Leave out `--native` to make a shortcut instead.

| Option | Meaning |
| :--- | :--- |
| `--native` | Put the app inside the CIA |
| `--title`, `--publisher` | Text on the HOME Menu (default: the app's own) |
| `--icon file.png` | Icon to use instead of the app's own |
| `--target /3ds/x/y.3dsx` | SD path of the file, when it is not on a mounted card |
| `--emulator PATH` | mGBA `.3dsx` (default: the first `mgba*.3dsx` under `SD:/3ds`) |
| `--arg VALUE`, `--deliver-arg TEXT` | Arguments for the app (shortcut mode only) |
| `--unique-id F9C19` | Fixed unique ID in `F8000`–`FEFFF` (default: derived from the path) |
| `-o file.cia` | Output file |

### Notes

- A native app gets no `argv`. Apps that find their files from `argv[0]` work only as shortcuts.
- A native GBA icon makes mGBA keep its saves in `SD:/mGBA/forwarders`, named after the ROM file.
  A GBA shortcut keeps them next to the ROM.
- On a New 3DS, native apps get the 124 MB memory mode and the 804 MHz CPU.
- To remove an icon, delete it in **System Settings > Data Management**. The app and its saves on
  the SD card stay.

## How it works

**Shortcut.** The stub (`stub/source/main.c`) reads the target path from its RomFS, checks that the
file and the loader title exist, and passes the path and `argv` to Luma's `hb:ldr` service. Then it
chainloads `000400000D921E00`. Luma builds that process from the `.3dsx` instead of the title's own
code. GBA shortcuts also pass the ROM path to mGBA as the APT deliver arg.

**Native.** `native.py` applies the `.3dsx` relocations for the application base address
`0x00100000`, writes the three segments as an ELF for makerom, and unpacks the app's RomFS into the
CIA's RomFS. A converted `mgba.3dsx` matches the code of mGBA's own CIA byte for byte.

**Website.** The page runs the same Python package in [Pyodide](https://pyodide.org) and calls
makerom and bannertool compiled to WebAssembly, so the browser and the command line share one
pipeline.

## Project layout

| Path | What |
| :--- | :--- |
| `src/shortcut3ds/` | The Python package: CLI, CIA pipeline, 3DSX and SMDH readers, banner art |
| `stub/` | The forwarder app, built with devkitARM and libctru |
| `web/` | The website; `scripts/build_web.sh` assembles it into `site/` |
| `tests/` | pytest suite, including a round trip through devkitPro's own `3dsxtool` |

## Development

```sh
make stub                  # stub.elf and stub.3dsx, in the devkitpro/devkitarm Docker image
pip install -e '.[dev]'
make test
scripts/build_web.sh       # the website in site/, needs Docker for Emscripten
python3 -m http.server -d site
```

CI builds the stub, runs ruff and pytest, and deploys the website to GitHub Pages from `main`.

## Licence

MIT, see [LICENSE](LICENSE). The website ships makerom, which contains GPL-3.0 code, as a separate
program; see [NOTICE.md](NOTICE.md) for every third-party component and its licence.

Not affiliated with Nintendo. Only use apps and ROMs that you own.
