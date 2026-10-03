# Input: a logo region from ctrtool --logo, taken from any CIA built with "Logo: Homebrew".

import sys
from pathlib import Path

from shortcut3ds import logo

source = Path(sys.argv[1]).read_bytes()
out = Path(__file__).parents[1] / "src" / "shortcut3ds" / "data" / "logo-black.bin"
out.write_bytes(logo.blacken(source))
print(f"wrote {out}")
