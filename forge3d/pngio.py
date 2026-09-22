"""Minimal dependency-free PNG encoder/decoder (8-bit RGB/RGBA)."""
import struct
import zlib

import numpy as np


def _chunk(tag, data):
    out = struct.pack(">I", len(data)) + tag + data
    out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return out


def write_png(path, rgb):
    """rgb: uint8 ndarray (H, W, 3) or (H, W, 4)."""
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
    h, w = rgb.shape[0], rgb.shape[1]
    if rgb.ndim == 2:
        rgb = np.stack([rgb] * 3, axis=-1)
    if rgb.shape[2] not in (3, 4):
        raise ValueError("PNG must have 3 or 4 channels")
    color = 6 if rgb.shape[2] == 4 else 2
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, color, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(raw, 6))
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def read_png(path):
    """Returns uint8 ndarray (H, W, 3). Supports 8-bit RGB/RGBA/gray, no interlace."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Not a PNG file")
    pos, idat, w, h, ctype = 8, [], 0, 0, 0
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        if tag == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", payload[:10])
            if depth != 8:
                raise ValueError("Only 8-bit PNG supported")
        elif tag == b"IDAT":
            idat.append(payload)
        elif tag == b"IEND":
            break
        pos += 12 + length
    raw = zlib.decompress(b"".join(idat))
    ch = {0: 1, 2: 3, 6: 4}[ctype]
    stride = w * ch
    out = np.zeros((h, stride), np.uint8)
    prev = np.zeros(stride, np.int32)
    for y in range(h):
        line = np.frombuffer(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)], np.uint8).astype(np.int32)
        f = raw[y * (stride + 1)]
        if f == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 0xFF
        elif f == 2:
            line = (line + prev) & 0xFF
        elif f == 3:
            for i in range(stride):
                left = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                left = line[i - ch] if i >= ch else 0
                up, ul = prev[i], (prev[i - ch] if i >= ch else 0)
                p = left + up - ul
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - ul)
                pr = left if (pa <= pb and pa <= pc) else (up if pb <= pc else ul)
                line[i] = (line[i] + pr) & 0xFF
        out[y] = line
        prev = line
    img = out.reshape(h, w, ch)
    if ch == 1:
        img = np.repeat(img, 3, axis=2)
    elif ch == 4:
        img = img[:, :, :3]
    return np.ascontiguousarray(img)
