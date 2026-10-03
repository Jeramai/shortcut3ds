# shortcut3ds

Put any 3DS homebrew app (`.3dsx`) or GBA ROM on the HOME Menu, from macOS or Linux.

`shortcut3ds` builds a small CIA that shows the app's own icon and name. When you open it, it asks
Luma3DS's homebrew loader to start the `.3dsx` from the SD card. The app itself stays where it is,
so its data files and updates keep working.

> **Status: alpha.** It is not yet tested on enough consoles. Report what happens on yours.

## Requirements

On the console:

- Luma3DS (any recent version, with its built-in `hb:ldr` homebrew loader).
- The **Homebrew Launcher Loader** title `000400000D921E00`. Install
  [`hblauncher_loader.cia`](https://github.com/yellows8/hblauncher_loader/releases) once with FBI.
  Luma replaces its code with the requested `.3dsx`, so the old version is fine.
- FBI, to install the shortcut.

On the computer: Python 3.10+ on macOS or Linux.

## Install

Download the `.whl` from the [latest release](https://github.com/Jeramai/shortcut3ds/releases/latest),
then:

```sh
pipx install ./shortcut3ds-*-py3-none-any.whl
shortcut3ds setup
```

`setup` downloads [`makerom`](https://github.com/3DSGuy/Project_CTR) and
[`bannertool`](https://github.com/carstene1ns/3ds-bannertool) to `~/.local/share/shortcut3ds/bin`
and checks their SHA-256. A copy on `PATH` wins, and so do `SHORTCUT3DS_MAKEROM` and
`SHORTCUT3DS_BANNERTOOL`.

## Use

Mount the SD card, then point at the `.3dsx` on it:

```sh
shortcut3ds make /Volumes/3DS/3ds/myapp/myapp.3dsx --install
```

This writes `myapp.cia` and copies it to `SD:/cia/`. On the console, open FBI, go to
**SD > cia**, and install it.

Options:

| Option | Meaning |
| :--- | :--- |
| `--target /3ds/x/y.3dsx` | SD path of the app, when the `.3dsx` is not on a mounted card |
| `--title`, `--publisher` | Text on the HOME Menu (default: the app's own) |
| `--arg VALUE` | Extra argument for the app; repeatable |
| `--deliver-arg TEXT` | Text passed to the app as the APT deliver arg |
| `--icon file.png` | Icon to use instead of the app's own |
| `--logo homebrew` | Show the homebrew splash while the app loads (default: no splash) |
| `--unique-id F9C19` | Fixed unique id (default: derived from the path, in `F8000`–`FEFFF`) |
| `-o file.cia` | Output file |

### GBA ROMs

```sh
shortcut3ds gba "/Volumes/3DS/roms/gba/Pokemon Emerald.gba" --install
```

The shortcut opens the ROM in mGBA. It sends the ROM path to mGBA as the APT deliver arg, so no
Nintendo files are involved and the ROM stays on the SD card. The icon shows the game's initials,
because GBA ROMs have no icon; pass `--icon cover.png` for a better one.

This needs an mGBA **development build** for 3DS (from
[mgba.io/downloads.html](https://mgba.io/downloads.html#development-downloads)) somewhere under
`SD:/3ds`. mGBA 0.10.x releases do not read a ROM path at startup. Use `--emulator` when the
`.3dsx` is not named `mgba*.3dsx`.

### Native mode

By default a shortcut is a small forwarder. The app runs inside the Homebrew Launcher Loader
title, so the HOME Menu shows that title while the app loads and when you close it.

With `--native`, the app goes inside the CIA and opens as its own title:

```sh
shortcut3ds make /Volumes/3DS/3ds/myapp/myapp.3dsx --native --install
shortcut3ds gba "/Volumes/3DS/roms/gba/Pokemon Emerald.gba" --native --install
```

- The CIA holds a copy of the app, so make it again after the app updates.
- The app gets no `argv`. Apps that find their files from `argv[0]` do not work this way.
- A native GBA shortcut holds mGBA and the ROM. mGBA keeps its saves in `SD:/mGBA/forwarders`,
  not next to the ROM.
- On a New 3DS, native apps get the 124 MB memory mode and the 804 MHz CPU.

### Remove a shortcut

To remove a shortcut, delete it in **System Settings > Data Management**. The app on the SD card
stays.

## How it works

The stub (`stub/source/main.c`) reads the target path from its RomFS. It checks that the file and
the loader title exist, and sends the path and `argv` to `hb:ldr`. Then it chainloads
`000400000D921E00`, with the deliver arg when there is one. Luma's loader builds that process from the `.3dsx` instead of the title's own
code. `argv[0]` is `sdmc:/…`, so the app can mount its own RomFS.

## Build

```sh
make stub          # builds stub.elf in the devkitpro/devkitarm Docker image
pip install -e '.[dev]'
make test
```

## Licence

MIT. `shortcut3ds` contains no Nintendo code, keys or content.
