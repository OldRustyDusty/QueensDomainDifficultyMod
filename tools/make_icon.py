"""Generate assets/icon.ico (a gold crown on purple) with no third-party packages.

    python tools/make_icon.py
"""
import os
import struct
import zlib

SIZES = (16, 24, 32, 48, 64, 128, 256)
SS = 4  # supersampling per axis

CROWN = [(0.20, 0.66), (0.17, 0.30), (0.355, 0.48), (0.50, 0.22), (0.645, 0.48), (0.83, 0.30), (0.80, 0.66)]
BAND = [(0.20, 0.69), (0.80, 0.69), (0.80, 0.78), (0.20, 0.78)]
JEWELS = [(0.17, 0.27, 0.055), (0.50, 0.19, 0.06), (0.83, 0.27, 0.055)]
TOP, BOTTOM = (0x7a, 0x4f, 0xb5), (0x3e, 0x1f, 0x66)
GOLD, GOLD_DARK = (0xf2, 0xc2, 0x4a), (0xc9, 0x8f, 0x1c)


def inside_poly(x, y, poly):
    c = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def inside_rounded(x, y, r=0.22, m=0.02):
    lo, hi = m, 1 - m
    if not (lo <= x <= hi and lo <= y <= hi):
        return False
    cx = min(max(x, lo + r), hi - r)
    cy = min(max(y, lo + r), hi - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def sample(x, y):
    if not inside_rounded(x, y):
        return None
    for jx, jy, jr in JEWELS:
        if (x - jx) ** 2 + (y - jy) ** 2 <= jr * jr:
            return GOLD
    if inside_poly(x, y, BAND):
        return GOLD_DARK
    if inside_poly(x, y, CROWN):
        return GOLD
    t = y
    return tuple(int(TOP[i] + (BOTTOM[i] - TOP[i]) * t) for i in range(3))


def render(n):
    rows = []
    for py in range(n):
        row = bytearray([0])
        for px in range(n):
            acc = [0, 0, 0]
            hits = 0
            for sy in range(SS):
                for sx in range(SS):
                    c = sample((px + (sx + 0.5) / SS) / n, (py + (sy + 0.5) / SS) / n)
                    if c:
                        hits += 1
                        for k in range(3):
                            acc[k] += c[k]
            if hits:
                row += bytes([acc[0] // hits, acc[1] // hits, acc[2] // hits, 255 * hits // (SS * SS)])
            else:
                row += b"\0\0\0\0"
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main():
    images = [render(n) for n in SIZES]
    out = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    offset = 6 + 16 * len(images)
    for n, png in zip(SIZES, images):
        out += struct.pack("<BBBBHHII", n % 256, n % 256, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
    for png in images:
        out += png
    dst = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")
    with open(dst, "wb") as f:
        f.write(out)
    print("wrote", dst, len(out), "bytes")


if __name__ == "__main__":
    main()
