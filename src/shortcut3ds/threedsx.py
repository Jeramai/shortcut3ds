import struct
from pathlib import Path

BASIC_HEADER_SIZE = 0x20


class ThreeDsxError(Exception):
    pass


def read_smdh(path: Path) -> bytes | None:
    with path.open("rb") as f:
        header = f.read(BASIC_HEADER_SIZE + 12)
        if len(header) < BASIC_HEADER_SIZE or header[:4] != b"3DSX":
            raise ThreeDsxError(f"{path} is not a 3DSX file")
        header_size = struct.unpack_from("<H", header, 4)[0]
        if header_size <= BASIC_HEADER_SIZE or len(header) < BASIC_HEADER_SIZE + 8:
            return None
        smdh_offset, smdh_size = struct.unpack_from("<II", header, BASIC_HEADER_SIZE)
        if smdh_size == 0:
            return None
        f.seek(smdh_offset)
        smdh = f.read(smdh_size)
    if smdh[:4] != b"SMDH":
        raise ThreeDsxError(f"{path} has a broken SMDH")
    return smdh
