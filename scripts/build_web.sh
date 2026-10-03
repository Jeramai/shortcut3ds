#!/usr/bin/env bash
# Assembles the static site in site/. Needs Docker, git, and python with `build` and Pillow.
set -euo pipefail
cd "$(dirname "$0")/.."

EMSDK=emscripten/emsdk:6.0.11
MAKEROM_TAG=makerom-v0.19.0
BANNERTOOL_COMMIT=734d33be79fd3f8c29c6296158f06ac7c5ca9dcb
MGBA_ZIP=https://github.com/Jeramai/shortcut3ds/releases/download/mgba-9146/mgba-3ds-9146.zip
MGBA_SHA256=6a76bfc7c47d14471b0b1bd055faf9985ba22c56bc391503f9fd776deca66bbe
SRC=build/src
WASM=build/wasm
EMFLAGS="-O2 -sMODULARIZE=1 -sEXPORTED_RUNTIME_METHODS=FS,callMain -sINVOKE_RUN=0 -sALLOW_MEMORY_GROWTH=1 -sEXIT_RUNTIME=0 -sENVIRONMENT=web,worker -sEXPORT_ES6=1"

mkdir -p "$SRC" "$WASM"
[ -d "$SRC/Project_CTR" ] || git clone -q --depth 1 --branch "$MAKEROM_TAG" https://github.com/3DSGuy/Project_CTR "$SRC/Project_CTR"
if [ ! -d "$SRC/bannertool" ]; then
  git clone -q https://github.com/carstene1ns/3ds-bannertool "$SRC/bannertool"
  git -C "$SRC/bannertool" checkout -q "$BANNERTOOL_COMMIT"
  perl -pi -e 's/u8 pad\[padLength\] = \{0\};/u8 pad[4] = {0};/' "$SRC/bannertool/source/3ds/lz11.cpp"
fi

if [ ! -f "$WASM/makerom.mjs" ]; then
  docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/w" -w "/w/$SRC/Project_CTR/makerom" "$EMSDK" sh -c "
    emcc $EMFLAGS -sEXPORT_NAME=createMakerom -std=gnu11 -Wno-everything \
      -Ideps/libblz/include -Ideps/libmbedtls/include -Ideps/libyaml/include \
      \$(find src deps/libblz/src deps/libmbedtls/src deps/libyaml/src -name '*.c') -o /w/$WASM/makerom.mjs"
fi
if [ ! -f "$WASM/bannertool.mjs" ]; then
  docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/w" -w "/w/$SRC/bannertool" "$EMSDK" sh -c "
    em++ $EMFLAGS -sEXPORT_NAME=createBannertool -std=c++17 -Wno-everything -Isource -Isource/pc \
      -DVERSION='\"1.2.3\"' -DSTBI_ONLY_PNG -DSTBI_NO_LINEAR -DSTBI_NO_STDIO \
      -DSTB_VORBIS_NO_PUSHDATA_API -DSTB_VORBIS_NO_STDIO -DDR_WAV_NO_STDIO \
      \$(find source -name '*.cpp') -o /w/$WASM/bannertool.mjs"
fi

[ -f src/shortcut3ds/data/stub.elf ] || { echo "src/shortcut3ds/data/stub.elf is missing: run make stub" >&2; exit 1; }
rm -rf build/dist site
python3 -m build --wheel --outdir build/dist >/dev/null
wheel=$(basename "$(ls build/dist)")

mkdir -p site/tools
cp web/index.html web/style.css web/app.js web/worker.js web/favicon.svg site/
for f in makerom.mjs makerom.wasm bannertool.mjs bannertool.wasm; do cp "$WASM/$f" site/tools/; done
[ -f build/mgba.zip ] || curl -sSfL -o build/mgba.zip "$MGBA_ZIP"
echo "$MGBA_SHA256  build/mgba.zip" | shasum -a 256 -c - >/dev/null
unzip -qo build/mgba.zip mgba.3dsx LICENSE -d build/mgba
cp build/mgba/mgba.3dsx site/tools/mgba.3dsx
cp build/mgba/LICENSE site/tools/mgba-LICENSE.txt
hash=$(shasum -a 256 "build/dist/$wheel" | cut -c1-12)
mkdir -p "site/py/$hash"
cp "build/dist/$wheel" "site/py/$hash/"
printf '{"wheel": "py/%s/%s"}\n' "$hash" "$wheel" > site/manifest.json
PYTHONPATH=src python3 -c "from shortcut3ds import web; print(web.describe())" > site/sources.json
echo "site/ is ready ($wheel)"
