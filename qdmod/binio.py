"""Tiny little-endian binary reader shared by the pak and uasset parsers."""
import struct


class Reader:
    """Sequential reader over a bytes-like object. `p` is the current position."""

    __slots__ = ("b", "p")

    def __init__(self, data, pos=0):
        self.b = data
        self.p = pos

    def take(self, n):
        if n < 0 or self.p + n > len(self.b):
            raise ValueError(f"read past end of buffer (pos {self.p}, want {n}, size {len(self.b)})")
        v = self.b[self.p:self.p + n]
        self.p += n
        return v

    def u8(self):
        return self.take(1)[0]

    def i32(self):
        return struct.unpack("<i", self.take(4))[0]

    def u32(self):
        return struct.unpack("<I", self.take(4))[0]

    def i64(self):
        return struct.unpack("<q", self.take(8))[0]

    def u64(self):
        return struct.unpack("<Q", self.take(8))[0]

    def fstr(self):
        """Unreal FString: int32 length (negative = UTF-16), NUL-terminated."""
        n = self.i32()
        if n == 0:
            return ""
        if n < 0:
            return self.take(-n * 2).decode("utf-16-le").rstrip("\0")
        return self.take(n).decode("utf-8", "replace").rstrip("\0")


def fstring_bytes(s):
    """Serialize an FString (ASCII/UTF-8 form) the way Unreal writes it."""
    b = s.encode("utf-8") + b"\0"
    return struct.pack("<i", len(b)) + b


def f32(x):
    """Round a Python float to the nearest 32-bit float and return it as bytes."""
    return struct.pack("<f", x)
