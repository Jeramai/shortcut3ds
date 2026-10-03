import struct


def lz11_decompress(src: bytes) -> bytes:
    if src[0] != 0x11:
        raise ValueError("not LZ11 data")
    size, i = int.from_bytes(src[1:4], "little"), 4
    if size == 0:
        size, i = int.from_bytes(src[4:8], "little"), 8
    out = bytearray()
    while len(out) < size:
        flags = src[i]
        i += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if not flags & (0x80 >> bit):
                out.append(src[i])
                i += 1
                continue
            b, ind = src[i], src[i] >> 4
            if ind == 0:
                n = ((b & 0xF) << 4 | src[i + 1] >> 4) + 0x11
                disp = ((src[i + 1] & 0xF) << 8 | src[i + 2]) + 1
                i += 3
            elif ind == 1:
                n = ((b & 0xF) << 12 | src[i + 1] << 4 | src[i + 2] >> 4) + 0x111
                disp = ((src[i + 2] & 0xF) << 8 | src[i + 3]) + 1
                i += 4
            else:
                n, disp = ind + 1, ((b & 0xF) << 8 | src[i + 1]) + 1
                i += 2
            for _ in range(n):
                out.append(out[-disp])
    return bytes(out)


def lz11_compress(data: bytes) -> bytes:
    out = bytearray([0x11]) + len(data).to_bytes(3, "little")
    index: dict[bytes, list[int]] = {}
    i, n = 0, len(data)
    while i < n:
        flag_pos, flags = len(out), 0
        out.append(0)
        for bit in range(8):
            if i >= n:
                break
            best_len = best_disp = 0
            for j in reversed(index.get(data[i : i + 3], [])[-64:]):
                if i - j > 0x1000:
                    break
                length = 0
                while length < 0x10110 and i + length < n and data[j + length] == data[i + length]:
                    length += 1
                if length > best_len:
                    best_len, best_disp = length, i - j
            if best_len >= 3:
                flags |= 0x80 >> bit
                d = best_disp - 1
                if best_len <= 0x10:
                    out += bytes([(best_len - 1) << 4 | d >> 8, d & 0xFF])
                elif best_len <= 0x110:
                    m = best_len - 0x11
                    out += bytes([m >> 4, (m & 0xF) << 4 | d >> 8, d & 0xFF])
                else:
                    m = best_len - 0x111
                    out += bytes([0x10 | m >> 12, m >> 4 & 0xFF, (m & 0xF) << 4 | d >> 8, d & 0xFF])
                step = best_len
            else:
                out.append(data[i])
                step = 1
            for k in range(i, min(i + step, n - 2)):
                index.setdefault(data[k : k + 3], []).append(k)
            i += step
        out[flag_pos] = flags
    return bytes(out)


def darc_files(darc: bytes) -> dict[str, tuple[int, int]]:
    if darc[:4] != b"darc":
        raise ValueError("not a DARC archive")
    table, _, _ = struct.unpack_from("<III", darc, 0x10)
    (count,) = struct.unpack_from("<I", darc, table + 8)
    names = table + count * 12
    files = {}
    for idx in range(count):
        name_off, offset, size = struct.unpack_from("<III", darc, table + idx * 12)
        end = start = names + (name_off & 0xFFFFFF)
        while darc[end : end + 2] != b"\0\0":
            end += 2
        if not name_off >> 24 & 1:
            files[darc[start:end].decode("utf-16-le")] = (offset, size)
    return files


def material_colours(darc: bytes) -> list[tuple[int, bytes, bytes]]:
    found = []
    for name, (off, _) in darc_files(darc).items():
        if not name.endswith(".bclyt"):
            continue
        (header,) = struct.unpack_from("<H", darc, off + 6)
        (sections,) = struct.unpack_from("<I", darc, off + 0x10)
        p = off + header
        for _ in range(sections):
            (size,) = struct.unpack_from("<I", darc, p + 4)
            if darc[p : p + 4] == b"mat1":
                (n,) = struct.unpack_from("<I", darc, p + 8)
                for o in struct.unpack_from(f"<{n}I", darc, p + 12):
                    found.append((p + o + 20, darc[p + o + 20 : p + o + 24], darc[p + o + 24 : p + o + 28]))
            p += size
    return found


def blacken(logo: bytes) -> bytes:
    darc = bytearray(lz11_decompress(logo))
    for offset, _, _ in material_colours(bytes(darc)):
        darc[offset + 4 : offset + 7] = b"\0\0\0"
    packed = lz11_compress(bytes(darc))
    if len(packed) > 0x2000:
        raise ValueError("the black logo does not fit in 0x2000 bytes")
    return packed + bytes(0x2000 - len(packed))
