# shortcut3ds

Put any 3DS homebrew app (`.3dsx`) on the HOME Menu, from macOS or Linux.

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

On the computer:

- Python 3.10+.
- [`makerom`](https://github.com/3DSGuy/Project_CTR/releases) and
  [`bannertool`](https://github.com/carstene1ns/3ds-bannertool) on `PATH`, or in `SHORTCUT3DS_MAKEROM`
  and `SHORTCUT3DS_BANNERTOOL`.

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
| `--unique-id F9C19` | Fixed unique id (default: derived from the path, in `F8000`–`FEFFF`) |
| `-o file.cia` | Output file |

To remove a shortcut, delete it in **System Settings > Data Management**. The app on the SD card
stays.

## How it works

The stub (`stub/source/main.c`) reads the target path from its RomFS. It checks that the file and
the loader title exist, and sends the path and `argv` to `hb:ldr`. Then it chainloads
`000400000D921E00`. Luma's loader builds that process from the `.3dsx` instead of the title's own
code. `argv[0]` is `sdmc:/…`, so the app can mount its own RomFS.

## Build

```sh
make stub          # builds stub.elf in the devkitpro/devkitarm Docker image
pip install -e '.[dev]'
make test
```

## Licence

MIT. `shortcut3ds` contains no Nintendo code, keys or content.
