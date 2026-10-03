# Third-party notices

shortcut3ds itself is MIT licensed (see `LICENSE`). It builds on, ships, or downloads the
components below. Each one keeps its own licence.

## Shipped by shortcut3ds

| Component | Where | Licence |
| :--- | :--- | :--- |
| [libctru](https://github.com/devkitPro/libctru) | linked into `stub.elf` (in the Python package) | zlib |
| [makerom](https://github.com/3DSGuy/Project_CTR) `makerom-v0.19.0` | `tools/makerom.wasm` on the website | MIT |
| ↳ libblz (CUE) | inside `makerom.wasm` | **GPL-3.0-or-later** |
| ↳ Mbed TLS | inside `makerom.wasm` | Apache-2.0 |
| ↳ LibYAML | inside `makerom.wasm` | MIT |
| [bannertool](https://github.com/carstene1ns/3ds-bannertool) `734d33b` | `tools/bannertool.wasm` on the website; release binaries | MIT |
| ↳ stb_image, stb_vorbis | inside bannertool | MIT or public domain |
| ↳ dr_wav | inside bannertool | MIT-0 or public domain |
| ↳ UTF8-CPP | inside bannertool | BSL-1.0 |
| [mGBA](https://mgba.io) development build 9146 | `tools/mgba.3dsx` on the website; release `mgba-9146`, which `shortcut3ds setup` downloads | MPL-2.0 |
| ↳ inih | inside mGBA | BSD-3-Clause |

Because `makerom.wasm` contains GPL-3.0 code, the website distributes it as a separate program
under the terms of the GPL. Its complete corresponding source is the upstream tag above.
`scripts/build_web.sh` fetches exactly that source and builds the WebAssembly file from it.
The bannertool binaries come from the pinned commit above with one change: an
initialised variable-length array in `source/3ds/lz11.cpp` becomes a fixed four-byte array,
so that Clang compiles it.

mGBA is shipped unmodified. Its source is commit
[`c3c8e5e`](https://github.com/mgba-emu/mgba/tree/c3c8e5e813f245028de118a56734e1dc0f35ce2a), and the
release zip contains its licence files. A native GBA icon puts this copy, or one that the user
chooses, inside the CIA.

The start logo in every CIA is makerom's built-in "Homebrew" logo.

## Loaded or downloaded, not shipped

- [Pyodide](https://pyodide.org) (MPL-2.0) and [Pillow](https://python-pillow.org) (MIT-CMU)
  load from the jsDelivr CDN when you use the website.
- `shortcut3ds setup` downloads makerom from the official Project_CTR release and checks its
  SHA-256.

## Not affiliated

Nintendo 3DS, HOME Menu and Game Boy Advance are trademarks of Nintendo. shortcut3ds is not
affiliated with or endorsed by Nintendo. Its own code contains no Nintendo code, keys or game data.
