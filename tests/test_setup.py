import hashlib
import io
import os
import zipfile

import pytest

from shortcut3ds import setup


def test_setup_rejects_a_download_with_the_wrong_hash(tmp_path, monkeypatch):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as z:
        z.writestr("makerom", b"binary")

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(setup.urllib.request, "urlopen", lambda *a, **k: Response(payload.getvalue()))
    with pytest.raises(setup.SetupError):
        setup.fetch(setup.Download("https://x/y.zip", "0" * 64, "makerom"), tmp_path / "makerom")
    assert not (tmp_path / "makerom").exists()

    good = hashlib.sha256(payload.getvalue()).hexdigest()
    setup.fetch(setup.Download("https://x/y.zip", good, "makerom"), tmp_path / "makerom")
    assert (tmp_path / "makerom").read_bytes() == b"binary"
    assert os.access(tmp_path / "makerom", os.X_OK)


def test_setup_downloads_the_included_mgba_on_every_platform():
    assert "mgba.3dsx" in setup.COMMON
    assert setup.COMMON["mgba.3dsx"].url.startswith(
        "https://github.com/Jeramai/shortcut3ds/releases/download/"
    )
